# connectors/mysql_source.py
from .base import DataSource
from typing import Any, Dict, List
import mysql.connector
import logging

# Настройка логирования для этого модуля
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)  # Создаем логгер для этого файла

class MySqlDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.connection = None

    def connect(self):
        try:
            logger.info("Attempting to connect to MySQL database...")
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
            logger.info("MySQL connection established successfully.")
        except mysql.connector.Error as err:
            # Логируем ошибку
            logger.error(f"MySQL connection failed: {err}")
            # Возбуждаем исключение дальше, если это необходимо для логики вызывающего кода
            raise Exception(f"MySQL connection failed: {err}")
        except Exception as e:
            # Логируем любые другие ошибки, которые могут возникнуть при подключении
            logger.error(f"An unexpected error occurred during MySQL connection: {e}")
            raise

    def fetch_data(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not self.connection or not self.connection.is_connected():
            error_msg = "Connection not established"
            logger.error(error_msg)
            raise Exception(error_msg)

        try:
            cursor = self.connection.cursor(dictionary=True)
            if params and not isinstance(params, list):  # params — словарь
                logger.debug(f"Executing query with params: {query}, params: {tuple(params.values())}")
                cursor.execute(query, tuple(params.values()) if isinstance(params, dict) else params)
            else:
                logger.debug(f"Executing query: {query}")
                cursor.execute(query)

            rows = cursor.fetchall()
            cursor.close()
            logger.info(f"Fetched {len(rows)} rows from database.")
            return [dict(row) for row in rows]
        except mysql.connector.Error as err:
            logger.error(f"Error fetching data: {err}")
            raise Exception(f"Error fetching data: {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during fetch_data: {e}")
            raise

    def build_select_query(self, table_name: str, fields: List[str] = None) -> str:
        # Формируем список полей
        if fields:
            fields_str = ', '.join(fields)
        else:
            fields_str = '*'

        query = f"SELECT {fields_str} FROM {table_name}"
        logger.debug(f"Built SELECT query: {query}")
        return query

    def get_schema(self) -> Dict[str, Any]:
        if not self.connection or not self.connection.is_connected():
            error_msg = "Connection not established"
            logger.error(error_msg)
            raise Exception(error_msg)

        try:
            cursor = self.connection.cursor(dictionary=True)
            logger.info("Fetching database schema...")

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
            logger.info(f"Fetched schema for {len(schema)} tables.")
            return schema
        except mysql.connector.Error as err:
            logger.error(f"Error fetching schema: {err}")
            raise Exception(f"Error fetching schema: {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during get_schema: {e}")
            raise
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()

    # --- Новые методы для INSERT, UPDATE, DELETE ---
    def insert_data(self, data: List[Dict[str, Any]], table_name: str):
        """
        Вставляет новые строки в таблицу MySQL.
        data: список словарей с данными
        table_name: имя таблицы
        """
        if not self.connection or not self.connection.is_connected():
            error_msg = "Connection not established"
            logger.error(error_msg)
            raise Exception(error_msg)

        if not data:
            logger.info("No data provided for insertion, skipping.")
            return # Нечего вставлять

        try:
            cursor = self.connection.cursor()
            logger.info(f"Attempting to insert {len(data)} rows into table '{table_name}'.")

            # Берем поля из первой строки данных
            first_row = data[0]
            columns = ", ".join([f"`{k}`" for k in first_row.keys()])
            placeholders = ", ".join(["%s"] * len(first_row))
            query = f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})"
            logger.debug(f"Generated INSERT query: {query}")

            for i, row in enumerate(data):
                cursor.execute(query, list(row.values()))
                logger.debug(f"Inserted row {i+1}: {row}")

            cursor.close()
            logger.info(f"Successfully inserted {len(data)} rows into table '{table_name}'.")
            # Autocommit включен, commit() не нужен
        except mysql.connector.Error as err:
            logger.error(f"Error inserting data: {err}")
            raise Exception(f"Error inserting data: {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during insert_data: {e}")
            raise

    def update_data(self, updates: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        """
        Обновляет строки в таблице MySQL на основе ключевых полей.
        updates: список словарей вида {"old": {...}, "new": {...}}
        key_fields: список ключевых полей для поиска
        table_name: имя таблицы
        """
        if not self.connection or not self.connection.is_connected():
            error_msg = "Connection not established"
            logger.error(error_msg)
            raise Exception(error_msg)

        if not updates:
            logger.info("No updates provided, skipping.")
            return # Нечего обновлять

        try:
            cursor = self.connection.cursor()
            logger.info(f"Attempting to update {len(updates)} rows in table '{table_name}'.")

            for i, update_item in enumerate(updates):
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
                logger.debug(f"Executing UPDATE query {i+1}: {query} with params {params}")

                cursor.execute(query, params)

            cursor.close()
            logger.info(f"Successfully updated {len(updates)} rows in table '{table_name}'.")
            # Autocommit включен, commit() не нужен
        except mysql.connector.Error as err:
            logger.error(f"Error updating data: {err}")
            raise Exception(f"Error updating data: {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during update_data: {e}")
            raise

    def delete_data(self, deletions: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        """
        Удаляет строки из таблицы MySQL на основе ключевых полей.
        deletions: список строк для удаления
        key_fields: список ключевых полей для поиска
        table_name: имя таблицы
        """
        if not self.connection or not self.connection.is_connected():
            error_msg = "Connection not established"
            logger.error(error_msg)
            raise Exception(error_msg)

        if not deletions:
            logger.info("No deletions provided, skipping.")
            return # Нечего удалять

        try:
            cursor = self.connection.cursor()
            logger.info(f"Attempting to delete {len(deletions)} rows from table '{table_name}'.")

            # WHERE часть
            where_parts = [f"`{k}` = %s" for k in key_fields]
            where_clause = " AND ".join(where_parts)
            query = f"DELETE FROM `{table_name}` WHERE {where_clause}"

            for i, del_row in enumerate(deletions):
                params = [del_row[k] for k in key_fields]
                logger.debug(f"Executing DELETE query {i+1}: {query} with params {params}")
                cursor.execute(query, params)

            cursor.close()
            logger.info(f"Successfully deleted {len(deletions)} rows from table '{table_name}'.")
            # Autocommit включен, commit() не нужен
        except mysql.connector.Error as err:
            logger.error(f"Error deleting data: {err}")
            raise Exception(f"Error deleting data: {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during delete_data: {e}")
            raise
    # ---------------------------------------------

    def disconnect(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("MySQL connection closed.")


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
                    try:
                        formatted_row[key] = value.decode('utf-8')
                    except UnicodeDecodeError as e:
                        logger.warning(f"Could not decode bytes for key '{key}': {e}. Using str representation.")
                        formatted_row[key] = str(value)
                elif isinstance(value, (bytearray,)):
                    formatted_row[key] = str(value)
                else:
                    formatted_row[key] = value
            formatted_data.append(formatted_row)
        logger.debug(f"Standard formatting completed for {len(formatted_data)} rows.")
        return formatted_data