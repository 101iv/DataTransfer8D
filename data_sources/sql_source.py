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
        # Включаем autocommit (isolation_level = None) для SQLite
        self.connection.isolation_level = None # <-- Включаем autocommit

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

    # --- Новые методы для INSERT, UPDATE, DELETE ---
    def insert_data(self, data: List[Dict[str, Any]], table_name: str):
        """
        Вставляет новые строки в таблицу SQLite.
        data: список словарей с данными
        table_name: имя таблицы
        """
        if not self.connection:
            raise Exception("Connection not established")

        if not data:
            return # Нечего вставлять

        cursor = self.connection.cursor()
        # Берем поля из первой строки данных
        first_row = data[0]
        columns = ", ".join([f"`{k}`" for k in first_row.keys()])
        placeholders = ", ".join(["?"] * len(first_row))
        query = f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})"

        for row in data:
            cursor.execute(query, list(row.values()))

        cursor.close()

    def update_data(self, updates: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        """
        Обновляет строки в таблице SQLite на основе ключевых полей.
        updates: список словарей вида {"old": {...}, "new": {...}}
        key_fields: список ключевых полей для поиска
        table_name: имя таблицы
        """
        if not self.connection:
            raise Exception("Connection not established")

        if not updates:
            return # Нечего обновлять

        cursor = self.connection.cursor()
        for update_item in updates:
            new_row = update_item["new"]
            old_row = update_item["old"]

            # SET часть
            set_parts = [f"`{k}` = ?" for k in new_row.keys()]
            set_clause = ", ".join(set_parts)
            # WHERE часть
            where_parts = [f"`{k}` = ?" for k in key_fields]
            where_clause = " AND ".join(where_parts)

            query = f"UPDATE `{table_name}` SET {set_clause} WHERE {where_clause}"
            # Параметры: сначала значения для SET, затем значения для WHERE
            params = list(new_row.values()) + [old_row[k] for k in key_fields]

            cursor.execute(query, params)

        cursor.close()
        # Autocommit включен, commit() не нужен

    def delete_data(self, deletions: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        """
        Удаляет строки из таблицы SQLite на основе ключевых полей.
        deletions: список строк для удаления
        key_fields: список ключевых полей для поиска
        table_name: имя таблицы
        """
        if not self.connection:
            raise Exception("Connection not established")

        if not deletions:
            return # Нечего удалять

        cursor = self.connection.cursor()
        # WHERE часть
        where_parts = [f"`{k}` = ?" for k in key_fields]
        where_clause = " AND ".join(where_parts)
        query = f"DELETE FROM `{table_name}` WHERE {where_clause}"

        for del_row in deletions:
            params = [del_row[k] for k in key_fields]
            cursor.execute(query, params)

        cursor.close()
        # Autocommit включен, commit() не нужен
    # ---------------------------------------------

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
