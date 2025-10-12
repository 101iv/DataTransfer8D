# data_sources.py
import sqlite3
import csv
from abc import ABC, abstractmethod
from typing import Any, Dict, List
import os

# Импортируем MySQL только при необходимости
mysql_available = False
try:
    import mysql.connector

    mysql_available = True
except ImportError:
    pass


# Базовый класс для источника данных
class DataSource(ABC):
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def fetch_data(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def disconnect(self):
        pass


# Реализация для SQL-базы (SQLite как пример)
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


# Реализация для MySQL
class MySqlDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        if not mysql_available:
            raise ImportError(
                "mysql-connector-python is required for MySQL support. Install it with: pip install mysql-connector-python")

        self.connection_params = connection_params
        self.connection = None

    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.connection_params.get("host", "localhost"),
                port=self.connection_params.get("port", 3306),
                user=self.connection_params.get("user", ""),
                password=self.connection_params.get("password", ""),
                database=self.connection_params.get("database", ""),
                charset=self.connection_params.get("charset", "utf8mb4"),
                use_unicode=True
            )
        except mysql.connector.Error as err:
            raise Exception(f"MySQL connection failed: {err}")

    def fetch_data(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not self.connection or not self.connection.is_connected():
            raise Exception("Connection not established")

        cursor = self.connection.cursor(dictionary=True)
        if params:
            cursor.execute(query, tuple(params.values()) if isinstance(params, dict) else params)
        else:
            cursor.execute(query)

        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]

    def get_schema(self) -> Dict[str, Any]:
        if not self.connection or not self.connection.is_connected():
            raise Exception("Connection not established")

        cursor = self.connection.cursor(dictionary=True)

        # Получаем список таблиц
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()

        schema = {}
        for table in tables:
            table_name = list(table.values())[0]  # MySQL возвращает результат в виде {'Tables_in_db': 'table_name'}

            # Получаем информацию о колонках
            cursor.execute(f"DESCRIBE `{table_name}`")
            columns = cursor.fetchall()

            schema[table_name] = [
                {
                    "name": col["Field"],
                    "type": col["Type"],
                    "not_null": col["Null"] == "NO",
                    "default": col["Default"],
                    "extra": col["Extra"]
                }
                for col in columns
            ]

        cursor.close()
        return schema

    def disconnect(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()


# Реализация для CSV-файла
class CSVDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.file_path = connection_params.get("path", "")
        self.delimiter = connection_params.get("delimiter", ",")

    def connect(self):
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"CSV file not found: {self.file_path}")

    def fetch_data(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        # В простой реализации query - это путь к файлу, params - фильтры
        with open(self.file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=self.delimiter)
            rows = [dict(row) for row in reader]

            # Применяем фильтрацию если задана
            if params and "filter" in params:
                filter_func = params["filter"]
                rows = [row for row in rows if filter_func(row)]

            return rows

    def get_schema(self) -> Dict[str, Any]:
        with open(self.file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=self.delimiter)
            fieldnames = reader.fieldnames
            # Простая схема - только имена колонок
            return {"columns": [{"name": name, "type": "TEXT"} for name in fieldnames]}

    def disconnect(self):
        pass  # Для CSV файлов нет необходимости в отключении