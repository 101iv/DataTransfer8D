# data_sources/mysql_source.py
from .base import DataSource
from typing import Any, Dict, List
import mysql.connector



class MySqlDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.connection = None

    def connect(self):
        try:
            # Включаем autocommit при подключении
            self.connection = mysql.connector.connect(
                host=self.connection_params.get("host", "localhost"),
                port=self.connection_params.get("port", 3306),
                user=self.connection_params.get("user", ""),
                password=self.connection_params.get("password", ""),
                database=self.connection_params.get("database", ""),
                charset=self.connection_params.get("charset", "utf8mb4"),
                use_unicode=True,
                autocommit=True  # <-- Включаем autocommit
            )
        except mysql.connector.Error as err:
            raise Exception(f"MySQL connection failed: {err}")

    def fetch_data(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not self.connection or not self.connection.is_connected():
            raise Exception("Connection not established")

        cursor = self.connection.cursor(dictionary=True)
        if params and not isinstance(params, list):  # params — словарь
            cursor.execute(query, tuple(params.values()) if isinstance(params, dict) else params)
        else:
            cursor.execute(query)

        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]

    def build_select_query(self, table_name: str, fields: List[str] = None) -> str:
        # Формируем список полей
        if fields:
            fields_str = ', '.join(fields)
        else:
            fields_str = '*'

        query = f"SELECT {fields_str} FROM {table_name}"

        return query

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

            # Получаем информацию о колонках, включая тип ключа
            cursor.execute(f"DESCRIBE `{table_name}`")
            columns = cursor.fetchall()

            schema[table_name] = [
                {
                    "name": col["Field"],
                    "type": col["Type"],
                    "not_null": col["Null"] == "NO",
                    "default": col["Default"],
                    "extra": col["Extra"],
                    "primary_key": col["Key"] == "PRI"  # Проверяем, является ли колонка первичным ключом
                }
                for col in columns
            ]

        cursor.close()
        return schema

    # --- Новые методы для INSERT, UPDATE, DELETE ---
    def insert_data(self, data: List[Dict[str, Any]], table_name: str):
        """
        Вставляет новые строки в таблицу MySQL.
        data: список словарей с данными
        table_name: имя таблицы
        """
        if not self.connection or not self.connection.is_connected():
            raise Exception("Connection not established")

        if not data:
            return # Нечего вставлять

        cursor = self.connection.cursor()
        # Берем поля из первой строки данных
        first_row = data[0]
        columns = ", ".join([f"`{k}`" for k in first_row.keys()])
        placeholders = ", ".join(["%s"] * len(first_row))
        query = f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})"

        for row in data:
            cursor.execute(query, list(row.values()))

        cursor.close()
        # Autocommit включен, commit() не нужен

    def update_data(self, updates: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        """
        Обновляет строки в таблице MySQL на основе ключевых полей.
        updates: список словарей вида {"old": {...}, "new": {...}}
        key_fields: список ключевых полей для поиска
        table_name: имя таблицы
        """
        if not self.connection or not self.connection.is_connected():
            raise Exception("Connection not established")

        if not updates:
            return # Нечего обновлять

        cursor = self.connection.cursor()
        for update_item in updates:
            new_row = update_item["new"]
            old_row = update_item["old"]

            # SET часть
            set_parts = [f"`{k}` = %s" for k in new_row.keys()]
            set_clause = ", ".join(set_parts)
            # WHERE часть
            where_parts = [f"`{k}` = %s" for k in key_fields]
            where_clause = " AND ".join(where_parts)

            query = f"UPDATE `{table_name}` SET {set_clause} WHERE {where_clause}"
            # Параметры: сначала значения для SET, затем значения для WHERE
            params = list(new_row.values()) + [old_row[k] for k in key_fields]

            cursor.execute(query, params)

        cursor.close()
        # Autocommit включен, commit() не нужен

    def delete_data(self, deletions: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        """
        Удаляет строки из таблицы MySQL на основе ключевых полей.
        deletions: список строк для удаления
        key_fields: список ключевых полей для поиска
        table_name: имя таблицы
        """
        if not self.connection or not self.connection.is_connected():
            raise Exception("Connection not established")

        if not deletions:
            return # Нечего удалять

        cursor = self.connection.cursor()
        # WHERE часть
        where_parts = [f"`{k}` = %s" for k in key_fields]
        where_clause = " AND ".join(where_parts)
        query = f"DELETE FROM `{table_name}` WHERE {where_clause}"

        for del_row in deletions:
            params = [del_row[k] for k in key_fields]
            cursor.execute(query, params)

        cursor.close()
        # Autocommit включен, commit() не нужен
    # ---------------------------------------------

    def disconnect(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()


    def standard_formatting(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
