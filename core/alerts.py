from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
import threading
import time
import streamlit as st
import pandas as pd
from sqlalchemy import text
from .storage import Storage
import json
import requests
import smtplib
import ssl
from email.message import EmailMessage


@dataclass
class AlertRule:
    name: str
    table: str
    column: str
    operator: str  # one of >, <, >=, <=, ==, !=
    threshold: float
    id: Optional[int] = None
    enabled: bool = True
    created_at: Optional[str] = None
    window_minutes: Optional[int] = None  # evaluate over last N minutes
    agg_func: Optional[str] = None  # one of 'last','avg','max','min'


def evaluate_rule(df: pd.DataFrame, rule: AlertRule) -> Optional[pd.DataFrame]:
    if df is None or df.empty or rule.column not in df.columns:
        return None
    # Optional time window
    if rule.window_minutes and 'ts' in df.columns:
        try:
            df = df.copy()
            df['ts'] = pd.to_datetime(df['ts'])
            cutoff = pd.Timestamp.utcnow() - pd.Timedelta(minutes=int(rule.window_minutes))
            df = df[df['ts'] >= cutoff]
        except Exception:
            pass
    if df.empty:
        return None

    # Optional aggregation
    series = df[rule.column]
    if rule.agg_func in {"avg", "mean"}:
        value = float(pd.to_numeric(series, errors='coerce').mean())
        df_eval = pd.DataFrame({rule.column: [value]})
    elif rule.agg_func == "max":
        value = float(pd.to_numeric(series, errors='coerce').max())
        df_eval = pd.DataFrame({rule.column: [value]})
    elif rule.agg_func == "min":
        value = float(pd.to_numeric(series, errors='coerce').min())
        df_eval = pd.DataFrame({rule.column: [value]})
    elif rule.agg_func == "last":
        value = pd.to_numeric(series, errors='coerce').iloc[-1]
        try:
            value = float(value)
        except Exception:
            return None
        df_eval = pd.DataFrame({rule.column: [value]})
    else:
        df_eval = df

    ops = {
        ">": lambda s, t: s > t,
        "<": lambda s, t: s < t,
        ">=": lambda s, t: s >= t,
        "<=": lambda s, t: s <= t,
        "==": lambda s, t: s == t,
        "!=": lambda s, t: s != t,
    }
    cond = ops.get(rule.operator, lambda s, t: s > t)(df_eval[rule.column], rule.threshold)
    hits = df_eval[cond]
    return hits if not hits.empty else None


def notify(rule: AlertRule, hits: pd.DataFrame):
    st.toast(f"Alert '{rule.name}' fired: {len(hits)} rows matched")


class AlertManager:
    def __init__(self, storage: Optional[Storage] = None):
        self.storage = storage or Storage()
        self._thread: Optional[threading.Thread] = None
        self._stop_event: Optional[threading.Event] = None
        self._interval_sec: int = 60
        self._ensure_tables()

    def _ensure_tables(self):
        ddl_rules = """
        CREATE TABLE IF NOT EXISTS alert_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            table_name TEXT NOT NULL,
            column TEXT NOT NULL,
            operator TEXT NOT NULL,
            threshold REAL NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            window_minutes INTEGER,
            agg_func TEXT
        )
        """
        ddl_events = """
        CREATE TABLE IF NOT EXISTS alert_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL,
            matched_count INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(rule_id) REFERENCES alert_rules(id)
        )
        """
        ddl_channels = """
        CREATE TABLE IF NOT EXISTS notification_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL, -- 'webhook' or 'smtp'
            config_json TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
        ddl_rule_map = """
        CREATE TABLE IF NOT EXISTS rule_channel_map (
            rule_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            PRIMARY KEY (rule_id, channel_id),
            FOREIGN KEY(rule_id) REFERENCES alert_rules(id),
            FOREIGN KEY(channel_id) REFERENCES notification_channels(id)
        )
        """
        with self.storage.engine.begin() as conn:
            conn.execute(text(ddl_rules))
            conn.execute(text(ddl_events))
            conn.execute(text(ddl_channels))
            conn.execute(text(ddl_rule_map))

        # Attempt to add new columns if DB existed before
        try:
            with self.storage.engine.begin() as conn:
                conn.execute(text("ALTER TABLE alert_rules ADD COLUMN window_minutes INTEGER"))
        except Exception:
            pass
        try:
            with self.storage.engine.begin() as conn:
                conn.execute(text("ALTER TABLE alert_rules ADD COLUMN agg_func TEXT"))
        except Exception:
            pass

    # CRUD operations
    def add_rule(self, rule: AlertRule) -> int:
        sql = text(
            """
            INSERT INTO alert_rules(name, table_name, column, operator, threshold, enabled, created_at, window_minutes, agg_func)
            VALUES(:name, :table_name, :column, :operator, :threshold, :enabled, :created_at, :window_minutes, :agg_func)
            """
        )
        params = {
            "name": rule.name,
            "table_name": rule.table,
            "column": rule.column,
            "operator": rule.operator,
            "threshold": float(rule.threshold),
            "enabled": 1 if rule.enabled else 0,
            "created_at": datetime.utcnow().isoformat(),
            "window_minutes": int(rule.window_minutes) if rule.window_minutes else None,
            "agg_func": rule.agg_func,
        }
        with self.storage.engine.begin() as conn:
            result = conn.execute(sql, params)
            rule_id = result.lastrowid if hasattr(result, "lastrowid") else conn.execute(text("SELECT last_insert_rowid()")).scalar()
        return int(rule_id)

    def list_rules(self) -> List[AlertRule]:
        sql = text("SELECT id, name, table_name, column, operator, threshold, enabled, created_at, window_minutes, agg_func FROM alert_rules ORDER BY id DESC")
        with self.storage.engine.begin() as conn:
            rows = conn.execute(sql).fetchall()
        rules: List[AlertRule] = []
        for r in rows:
            rules.append(
                AlertRule(
                    id=r[0], name=r[1], table=r[2], column=r[3], operator=r[4], threshold=r[5], enabled=bool(r[6]), created_at=r[7], window_minutes=r[8], agg_func=r[9]
                )
            )
        return rules

    def set_enabled(self, rule_id: int, enabled: bool) -> None:
        sql = text("UPDATE alert_rules SET enabled=:enabled WHERE id=:id")
        with self.storage.engine.begin() as conn:
            conn.execute(sql, {"enabled": 1 if enabled else 0, "id": rule_id})

    def delete_rule(self, rule_id: int) -> None:
        with self.storage.engine.begin() as conn:
            conn.execute(text("DELETE FROM alert_events WHERE rule_id=:id"), {"id": rule_id})
            conn.execute(text("DELETE FROM alert_rules WHERE id=:id"), {"id": rule_id})

    # Events
    def record_event(self, rule_id: int, matched_count: int) -> None:
        sql = text(
            "INSERT INTO alert_events(rule_id, matched_count, created_at) VALUES(:rule_id, :matched_count, :created_at)"
        )
        with self.storage.engine.begin() as conn:
            conn.execute(sql, {"rule_id": rule_id, "matched_count": matched_count, "created_at": datetime.utcnow().isoformat()})
        # After recording, send notifications via channels
        try:
            self._send_notifications_for_rule(rule_id, matched_count)
        except Exception:
            pass

    def list_events(self, limit: int = 50):
        sql = text(
            """
            SELECT e.id, e.rule_id, r.name, e.matched_count, e.created_at
            FROM alert_events e JOIN alert_rules r ON e.rule_id=r.id
            ORDER BY e.id DESC LIMIT :lim
            """
        )
        with self.storage.engine.begin() as conn:
            rows = conn.execute(sql, {"lim": limit}).fetchall()
        return rows

    # Evaluation
    def evaluate_all_once(self):
        rules = [r for r in self.list_rules() if r.enabled]
        for rule in rules:
            try:
                df = self.storage.read_table(rule.table, limit=2000)
                hits = evaluate_rule(df, rule)
                if hits is not None and len(hits) > 0:
                    self.record_event(rule.id, len(hits))
            except Exception:
                continue

    # Scheduler control
    def start_scheduler(self, interval_sec: int = 60):
        if self._thread and self._thread.is_alive():
            self._interval_sec = interval_sec
            return
        self._interval_sec = interval_sec
        self._stop_event = threading.Event()

        def _loop():
            while self._stop_event and not self._stop_event.is_set():
                try:
                    self.evaluate_all_once()
                except Exception:
                    pass
                finally:
                    self._stop_event.wait(self._interval_sec)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop_scheduler(self):
        if self._stop_event:
            self._stop_event.set()

    def is_scheduler_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # Channels CRUD
    def add_channel(self, name: str, type_: str, config: Dict[str, Any], enabled: bool = True) -> int:
        sql = text(
            """
            INSERT INTO notification_channels(name, type, config_json, enabled, created_at)
            VALUES(:name, :type, :config_json, :enabled, :created_at)
            """
        )
        with self.storage.engine.begin() as conn:
            res = conn.execute(sql, {
                "name": name,
                "type": type_,
                "config_json": json.dumps(config),
                "enabled": 1 if enabled else 0,
                "created_at": datetime.utcnow().isoformat(),
            })
            cid = res.lastrowid if hasattr(res, 'lastrowid') else conn.execute(text("SELECT last_insert_rowid()")).scalar()
        return int(cid)

    def list_channels(self) -> List[Dict[str, Any]]:
        sql = text("SELECT id, name, type, config_json, enabled, created_at FROM notification_channels ORDER BY id DESC")
        with self.storage.engine.begin() as conn:
            rows = conn.execute(sql).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r[0],
                "name": r[1],
                "type": r[2],
                "config": json.loads(r[3]) if r[3] else {},
                "enabled": bool(r[4]),
                "created_at": r[5],
            })
        return out

    def delete_channel(self, channel_id: int) -> None:
        with self.storage.engine.begin() as conn:
            conn.execute(text("DELETE FROM rule_channel_map WHERE channel_id=:cid"), {"cid": channel_id})
            conn.execute(text("DELETE FROM notification_channels WHERE id=:cid"), {"cid": channel_id})

    def set_channel_enabled(self, channel_id: int, enabled: bool) -> None:
        with self.storage.engine.begin() as conn:
            conn.execute(text("UPDATE notification_channels SET enabled=:en WHERE id=:cid"), {"en": 1 if enabled else 0, "cid": channel_id})

    def map_rule_channel(self, rule_id: int, channel_id: int) -> None:
        with self.storage.engine.begin() as conn:
            conn.execute(text("INSERT OR IGNORE INTO rule_channel_map(rule_id, channel_id) VALUES(:rid, :cid)"), {"rid": rule_id, "cid": channel_id})

    def unmap_rule_channel(self, rule_id: int, channel_id: int) -> None:
        with self.storage.engine.begin() as conn:
            conn.execute(text("DELETE FROM rule_channel_map WHERE rule_id=:rid AND channel_id=:cid"), {"rid": rule_id, "cid": channel_id})

    def channels_for_rule(self, rule_id: int) -> List[Dict[str, Any]]:
        sql = text(
            """
            SELECT c.id, c.name, c.type, c.config_json, c.enabled, c.created_at
            FROM notification_channels c JOIN rule_channel_map m ON c.id=m.channel_id
            WHERE m.rule_id=:rid
            """
        )
        with self.storage.engine.begin() as conn:
            rows = conn.execute(sql, {"rid": rule_id}).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r[0],
                "name": r[1],
                "type": r[2],
                "config": json.loads(r[3]) if r[3] else {},
                "enabled": bool(r[4]),
                "created_at": r[5],
            })
        return out

    # Notification sending
    def _send_notifications_for_rule(self, rule_id: int, matched_count: int):
        chans = self.channels_for_rule(rule_id)
        for ch in chans:
            if not ch.get('enabled', True):
                continue
            try:
                if ch['type'] == 'webhook':
                    self._send_webhook(ch['config'], rule_id, matched_count)
                elif ch['type'] == 'smtp':
                    self._send_email(ch['config'], rule_id, matched_count)
            except Exception:
                continue

    def _send_webhook(self, config: Dict[str, Any], rule_id: int, matched_count: int):
        url = config.get('url')
        if not url:
            return
        headers = config.get('headers') or {"Content-Type": "application/json"}
        payload = {
            "rule_id": rule_id,
            "matched_count": matched_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
        requests.post(url, headers=headers, json=payload, timeout=5)

    def _send_email(self, config: Dict[str, Any], rule_id: int, matched_count: int):
        host = config.get('host')
        port = int(config.get('port', 587))
        username = config.get('username')
        password = config.get('password')
        from_addr = config.get('from')
        to_addr = config.get('to')
        use_tls = bool(config.get('use_tls', True))
        if not (host and from_addr and to_addr):
            return
        msg = EmailMessage()
        msg['Subject'] = f"Alert fired for rule {rule_id}"
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg.set_content(f"Rule {rule_id} matched {matched_count} rows at {datetime.utcnow().isoformat()}.")
        if use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.starttls(context=context)
                if username and password:
                    server.login(username, password)
                server.send_message(msg)

    def send_test_channel(self, channel_id: int) -> None:
        # Send a test notification (does not record an event)
        with self.storage.engine.begin() as conn:
            row = conn.execute(text("SELECT id, name, type, config_json, enabled FROM notification_channels WHERE id=:cid"), {"cid": channel_id}).fetchone()
        if not row:
            return
        ch = {
            "id": row[0],
            "name": row[1],
            "type": row[2],
            "config": json.loads(row[3]) if row[3] else {},
            "enabled": bool(row[4]),
        }
        if not ch.get("enabled", True):
            return
        try:
            if ch['type'] == 'webhook':
                self._send_webhook(ch['config'], rule_id=0, matched_count=0)
            elif ch['type'] == 'smtp':
                # Send an informational email
                cfg = ch['config']
                host = cfg.get('host')
                port = int(cfg.get('port', 587))
                username = cfg.get('username')
                password = cfg.get('password')
                from_addr = cfg.get('from')
                to_addr = cfg.get('to')
                use_tls = bool(cfg.get('use_tls', True))
                if not (host and from_addr and to_addr):
                    return
                msg = EmailMessage()
                msg['Subject'] = "Test: Big Data Platform Alert Channel"
                msg['From'] = from_addr
                msg['To'] = to_addr
                msg.set_content("This is a test notification from the Big Data Analytics Platform.")
                if use_tls:
                    context = ssl.create_default_context()
                    with smtplib.SMTP(host, port, timeout=10) as server:
                        server.starttls(context=context)
                        if username and password:
                            server.login(username, password)
                        server.send_message(msg)
                else:
                    with smtplib.SMTP(host, port, timeout=10) as server:
                        if username and password:
                            server.login(username, password)
                        server.send_message(msg)
        except Exception:
            pass
        else:
            with smtplib.SMTP(host, port, timeout=10) as server:
                if username and password:
                    server.login(username, password)
                server.send_message(msg)
