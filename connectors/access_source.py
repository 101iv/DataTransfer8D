# connectors/access_source.py
from .base import DataSource
from typing import Any, Dict, List
import pyodbc
import logging

# Настройка логирования для этого модуля
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)  # Создаем логгер для этого файла

class AccessDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        # Ожидаем, что connection_params будет содержать 'db_path' - путь к .mdb или .accdb файлу
        self.db_path = connection_params.get("db_path")
        if not self.db_path:
            error_msg = "Connection parameter 'db_path' is required for Access database."
            logger.error(error_msg)
            raise ValueError(error_msg)
        self.connection_string = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={self.db_path};"
        logger.debug(f"Initialized AccessDataSource with connection string: {self.connection_string.replace(self.db_path, '***masked_path***')}")
        self.connection = None

    def connect(self):
        try:
            logger.info(f"Attempting to connect to Access database at: {self.db_path}")
            self.connection = pyodbc.connect(self.connection_string)
            # Устанавливаем autocommit вручную, если поддерживается
            self.connection.autocommit = True
            logger.info("Access connection established successfully.")
        except pyodbc.Error as err:
            logger.error(f"Access connection failed: {err}")
            raise Exception(f"Access connection failed: {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during Access connection: {e}")
            raise

    def fetch_data(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not self.connection:
            error_msg = "Connection not established"
            logger.error(error_msg)
            raise Exception(error_msg)

        try:
            cursor = self.connection.cursor()
            if params:
                # pyodbc ожидает параметры в виде кортежа
                params_tuple = tuple(params.values()) if isinstance(params, dict) else params
                logger.debug(f"Executing query with params: {query}, params: {params_tuple}")
                cursor.execute(query, params_tuple)
            else:
                logger.debug(f"Executing query: {query}")
                cursor.execute(query)

            # Получаем имена колонок
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            cursor.close()
            logger.info(f"Fetched {len(rows)} rows from database.")
            # Возвращаем список словарей
            return [dict(zip(columns, row)) for row in rows]
        except pyodbc.Error as err:
            logger.error(f"Error fetching data: {err}")
            raise Exception(f"Error fetching data: {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during fetch_data: {e}")
            raise

    def build_select_query(self, table_name: str, fields: List[str] = None) -> str:
        # Формируем список полей
        if fields:
            # Защита имен полей в квадратных скобках
            fields_str = ', '.join([f"[{field}]" for field in fields])
        else:
            fields_str = '*'

        # Защита имени таблицы в квадратных скобках
        query = f"SELECT {fields_str} FROM [{table_name}]"
        logger.debug(f"Built SELECT query: {query}")
        return query

    def get_schema(self) -> Dict[str, Any]:
        if not self.connection:
            error_msg = "Connection not established"
            logger.error(error_msg)
            raise Exception(error_msg)

        try:
            cursor = self.connection.cursor()
            logger.info("Fetching database schema...")

            # Получаем список таблиц (исключая системные)
            cursor.execute("""
                SELECT Name
                FROM MSysObjects
                WHERE Type=1 AND Flags=0 AND Name NOT LIKE 'MSys*'
            """)
            table_names = [row[0] for row in cursor.fetchall()]

            schema = {}
            for table_name in table_names:
                # Получаем информацию о полях таблицы
                # pyodbc.columns возвращает информацию о столбцах
                cursor.columns(table=table_name)
                columns_info = cursor.fetchall()

                schema[table_name] = []
                for col_info in columns_info:
                    # col_info[3] - COLUMN_NAME
                    # col_info[5] - DATA_TYPE (pyodbc type code)
                    # col_info[6] - TYPE_NAME (string representation like 'TEXT', 'LONG', 'DATE', etc.)
                    # col_info[10] - NULLABLE (0 - NO, 1 - YES)
                    # col_info[17] - IS_NULLABLE ('NO', 'YES')
                    # col_info[22] - IS_AUTOINCREMENT ('YES', 'NO', None)

                    # Для определения первичного ключа используем индексы
                    # Сначала получим список первичных ключей для таблицы
                    pk_columns = self._get_primary_keys(cursor, table_name)

                    col_name = col_info[3]
                    type_name = col_info[6]
                    is_nullable = col_info[17] == 'YES'
                    is_autoincrement = col_info[22] == 'YES'

                    schema[table_name].append({
                        "name": col_name,
                        "type": type_name,
                        "not_null": not is_nullable,
                        "default": None, # Access не всегда предоставляет информацию о DEFAULT через pyodbc
                        "extra": "autoincrement" if is_autoincrement else "",
                        "primary_key": col_name in pk_columns
                    })
            logger.info(f"Fetched schema for {len(schema)} tables.")
            return schema
        except pyodbc.Error as err:
            logger.error(f"Error fetching schema: {err}")
            raise Exception(f"Error fetching schema: {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during get_schema: {e}")
            raise
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()

    def _get_primary_keys(self, cursor, table_name: str) -> List[str]:
        """Вспомогательный метод для получения списка первичных ключей таблицы."""
        try:
            logger.debug(f"Fetching primary keys for table '{table_name}'.")
            # Используем pyodbc.primaryKeys
            cursor.primaryKeys(table=table_name)
            pk_info = cursor.fetchall()
            pk_columns = [row[3] for row in pk_info] # row[3] - COLUMN_NAME
            logger.debug(f"Found primary keys for '{table_name}': {pk_columns}")
            return pk_columns
        except Exception as e:
            logger.warning(f"Could not fetch primary keys for table '{table_name}': {e}. Returning empty list.")
            return []


    # --- Новые методы для INSERT, UPDATE, DELETE ---
    def insert_data(self, data: List[Dict[str, Any]], table_name: str):
        """
        Вставляет новые строки в таблицу Access.
        data: список словарей с данными
        table_name: имя таблицы
        """
        if not self.connection:
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
            # Защита имен полей в квадратных скобках
            columns = ", ".join([f"[{k}]" for k in first_row.keys()])
            placeholders = ", ".join(["?"] * len(first_row))
            query = f"INSERT INTO [{table_name}] ({columns}) VALUES ({placeholders})"
            logger.debug(f"Generated INSERT query: {query}")

            for i, row in enumerate(data):
                cursor.execute(query, list(row.values()))
                logger.debug(f"Inserted row {i+1}: {row}")

            cursor.close()
            logger.info(f"Successfully inserted {len(data)} rows into table '{table_name}'.")
            # Autocommit включен, commit() не нужен
        except pyodbc.Error as err:
            logger.error(f"Error inserting data: {err}")
            raise Exception(f"Error inserting data: {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during insert_data: {e}")
            raise

    def update_data(self, updates: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        """
        Обновляет строки в таблице Access на основе ключевых полей.
        updates: список словарей вида {"old": {...}, "new": {...}}
        key_fields: список ключевых полей для поиска
        table_name: имя таблицы
        """
        if not self.connection:
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

                # SET часть - защищаем имена полей
                set_parts = [f"[{k}] = ?" for k in new_row.keys()]
                set_clause = ", ".join(set_parts)
                # WHERE часть - защищаем имена полей
                where_parts = [f"[{k}] = ?" for k in key_fields]
                where_clause = " AND ".join(where_parts)

                query = f"UPDATE [{table_name}] SET {set_clause} WHERE {where_clause}"
                # Параметры: сначала значения для SET, затем значения для WHERE
                params = list(new_row.values()) + [old_row[k] for k in key_fields]
                logger.debug(f"Executing UPDATE query {i+1}: {query} with params {params}")

                cursor.execute(query, params)

            cursor.close()
            logger.info(f"Successfully updated {len(updates)} rows in table '{table_name}'.")
            # Autocommit включен, commit() не нужен
        except pyodbc.Error as err:
            logger.error(f"Error updating data: {err}")
            raise Exception(f"Error updating data: {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during update_data: {e}")
            raise

    def delete_data(self, deletions: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        """
        Удаляет строки из таблицы Access на основе ключевых полей.
        deletions: список строк для удаления
        key_fields: список ключевых полей для поиска
        table_name: имя таблицы
        """
        if not self.connection:
            error_msg = "Connection not established"
            logger.error(error_msg)
            raise Exception(error_msg)

        if not deletions:
            logger.info("No deletions provided, skipping.")
            return # Нечего удалять

        try:
            cursor = self.connection.cursor()
            logger.info(f"Attempting to delete {len(deletions)} rows from table '{table_name}'.")

            # WHERE часть - защищаем имена полей
            where_parts = [f"[{k}] = ?" for k in key_fields]
            where_clause = " AND ".join(where_parts)
            query = f"DELETE FROM [{table_name}] WHERE {where_clause}"

            for i, del_row in enumerate(deletions):
                params = [del_row[k] for k in key_fields]
                logger.debug(f"Executing DELETE query {i+1}: {query} with params {params}")
                cursor.execute(query, params)

            cursor.close()
            logger.info(f"Successfully deleted {len(deletions)} rows from table '{table_name}'.")
            # Autocommit включен, commit() не нужен
        except pyodbc.Error as err:
            logger.error(f"Error deleting data: {err}")
            raise Exception(f"Error deleting data: {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during delete_data: {e}")
            raise
    # ---------------------------------------------


    def disconnect(self):
        if self.connection:
            self.connection.close()
            logger.info("Access connection closed.")

    def standard_formatting(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Стандартное форматирование данных после выборки из Access
        """
        formatted_data = []
        for row in data:
            formatted_row = {}
            for key, value in row.items():
                # Приведение типов данных
                if isinstance(value, bytes):
                    try:
                        formatted_row[key] = value.decode('utf-8', errors='replace')
                    except UnicodeDecodeError as e:
                        logger.warning(f"Could not decode bytes for key '{key}': {e}. Using str representation.")
                        formatted_row[key] = str(value)
                elif isinstance(value, (bytearray,)):
                    formatted_row[key] = str(value)
                # Access может возвращать datetime.date или datetime.datetime
                # Оставляем их как есть, если не нужно специальное форматирование
                else:
                    formatted_row[key] = value
            formatted_data.append(formatted_row)
        logger.debug(f"Standard formatting completed for {len(formatted_data)} rows.")
        return formatted_data