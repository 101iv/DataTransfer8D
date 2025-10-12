# data_sources/mysql_source.py
from .base import DataSource
from typing import Any, Dict, List

# Импортируем MySQL только при необходимости
mysql_available = False
try:
    import mysql.connector

    mysql_available = True
except ImportError:
    pass


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


def standard_formatting(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Стандартное форматирование данных после выборки из MySQL
    """
    formatted_data = []
    for row in data:
        formatted_row = {}
        for key, value in row.items():
            # Приведение типов данных
            if isinstance(value, bytes):
                formatted_row[key] = value.decode('utf-8')
            elif isinstance(value, (bytearray,)):
                formatted_row[key] = str(value)
            else:
                formatted_row[key] = value
        formatted_data.append(formatted_row)
    return formatted_data