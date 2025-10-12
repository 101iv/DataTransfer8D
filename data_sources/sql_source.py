# data_sources/sql_source.py
import sqlite3
from .base import DataSource
from typing import Any, Dict, List


class SQLDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.connection = None

    def connect(self):
        db_path = self.connection_params.get("path", ":memory:")
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row  # Для доступа к колонкам по имени

    def fetch_data(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not self.connection:
            raise Exception("Connection not established")

        cursor = self.connection.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_schema(self) -> Dict[str, Any]:
        if not self.connection:
            raise Exception("Connection not established")

        cursor = self.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        schema = {}
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            schema[table_name] = [
                {"name": col[1], "type": col[2], "not_null": bool(col[3]), "default": col[4],
                 "primary_key": bool(col[5])}
                for col in columns
            ]

        return schema

    def disconnect(self):
        if self.connection:
            self.connection.close()


def standard_formatting(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Стандартное форматирование данных после выборки из SQLite
    """
    formatted_data = []
    for row in data:
        formatted_row = {}
        for key, value in row.items():
            # Приведение типов данных
            if isinstance(value, bytes):
                formatted_row[key] = value.decode('utf-8')
            else:
                formatted_row[key] = value
        formatted_data.append(formatted_row)
    return formatted_data