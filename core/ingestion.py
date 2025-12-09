import time
import threading
from typing import Callable, Optional
import pandas as pd
from .storage import Storage


class IngestionManager:
    def __init__(self, storage: Storage):
        self.storage = storage
        self._threads = {}
        self._stops = {}

    def start_pipeline(
        self, name: str, fetch_fn: Callable[[], pd.DataFrame], interval_sec: int = 10
    ) -> None:
        if name in self._threads and self._threads[name].is_alive():
            return
        stop_event = threading.Event()
        self._stops[name] = stop_event

        def _run():
            while not stop_event.is_set():
                try:
                    df = fetch_fn()
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        self.storage.append_dataframe(name, df)
                except Exception:
                    pass
                finally:
                    stop_event.wait(interval_sec)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        self._threads[name] = t

    def stop_pipeline(self, name: str) -> None:
        ev = self._stops.get(name)
        if ev:
            ev.set()

    def is_running(self, name: str) -> bool:
        t = self._threads.get(name)
        return t.is_alive() if t else False

    def list_pipelines(self):
        return list(self._threads.keys())
