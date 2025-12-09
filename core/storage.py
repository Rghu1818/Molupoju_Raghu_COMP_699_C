from pathlib import Path
from typing import Optional
import pandas as pd
from sqlalchemy import create_engine, inspect
from .config import DB_PATH, DATA_DIR


class Storage:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        uri = f"sqlite:///{db_path.as_posix()}"
        self.engine = create_engine(uri, echo=False)

    def append_dataframe(self, table: str, df: pd.DataFrame):
        if df is None or df.empty:
            return
        df.to_sql(table, self.engine, if_exists="append", index=False)

    def read_table(self, table: str, limit: Optional[int] = None) -> pd.DataFrame:
        q = f"SELECT * FROM {table}"
        if limit:
            q += f" ORDER BY ROWID DESC LIMIT {int(limit)}"
        return pd.read_sql(q, self.engine)

    def list_tables(self) -> list:
        insp = inspect(self.engine)
        return insp.get_table_names()
