# connectors/sql_source.py
import re
import sqlite3
from datetime import datetime, date
import logging

from .base import DataSource
from typing import Any, Dict, List


# Настройка логирования для этого модуля
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)  # Создаем логгер для этого файла

class SQLDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.connection = None
        logger.debug(f"Initialized SQLDataSource with params: {connection_params}")

    def connect(self):
        try:
            db_path = self.connection_params.get("path", ":memory:")
            logger.info(f"Attempting to connect to SQLite database at: {db_path}")
            self.connection = sqlite3.connect(db_path)
            self.connection.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
            # Включаем autocommit (isolation_level = None) для SQLite
            self.connection.isolation_level = None # <-- Включаем autocommit
            logger.info("SQLite connection established successfully.")
        except sqlite3.Error as err:
            logger.error(f"SQLite connection failed: {err}")
            raise Exception(f"SQLite connection failed: {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during SQLite connection: {e}")
            raise

    def fetch_data(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not self.connection:
            error_msg = "Connection not established"
            logger.error(error_msg)
            raise Exception(error_msg)

        try:
            cursor = self.connection.cursor()
            if params:
                logger.debug(f"Executing query with params: {query}, params: {params}")
                cursor.execute(query, params)
            else:
                logger.debug(f"Executing query: {query}")
                cursor.execute(query)

            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            logger.info(f"Fetched {len(result)} rows from database.")
            return result
        except sqlite3.Error as err:
            logger.error(f"Error fetching  {err}")
            raise Exception(f"Error fetching  {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during fetch_ {e}")
            raise

    def get_schema(self) -> Dict[str, Any]:
        if not self.connection:
            error_msg = "Connection not established"
            logger.error(error_msg)
            raise Exception(error_msg)

        try:
            cursor = self.connection.cursor()
            logger.info("Fetching database schema...")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            schema = {}
            for table in tables:
                table_name = table[0]
                logger.debug(f"Fetching schema for table: {table_name}")
                cursor.execute(f"PRAGMA table_info(`{table_name}`)")
                columns = cursor.fetchall()
                schema[table_name] = [
                    {
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "default": col[4],
                        "primary_key": bool(col[5])  # Используем значение из PRAGMA table_info
                    }
                    for col in columns
                ]
            logger.info(f"Fetched schema for {len(schema)} tables.")
            return schema
        except sqlite3.Error as err:
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
        Вставляет новые строки в таблицу SQLite.
        data: список словарей с данными
        table_name: имя таблицы
        """
        if not self.connection:
            error_msg = "Connection not established"
            logger.error(error_msg)
            raise Exception(error_msg)

        if not data:
            return # Нечего вставлять

        try:
            cursor = self.connection.cursor()
            logger.info(f"Attempting to insert {len(data)} rows into table '{table_name}'.")

            # Берем поля из первой строки данных
            first_row = data[0]
            columns = ", ".join([f"`{k}`" for k in first_row.keys()])
            placeholders = ", ".join(["?"] * len(first_row))
            query = f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})"
            logger.debug(f"Generated INSERT query: {query}")

            for i, row in enumerate(data):
                cursor.execute(query, list(row.values()))
                logger.debug(f"Inserted row {i+1}: {row}")

            cursor.close()
            logger.info(f"Successfully inserted {len(data)} rows into table '{table_name}'.")
        except sqlite3.Error as err:
            logger.error(f"Error inserting  {err}")
            raise Exception(f"Error inserting  {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during insert_ {e}")
            raise

    def update_data(self, updates: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        """
        Обновляет строки в таблице SQLite на основе ключевых полей.
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

                # SET часть
                set_parts = [f"`{k}` = ?" for k in new_row.keys()]
                set_clause = ", ".join(set_parts)
                # WHERE часть
                where_parts = [f"`{k}` = ?" for k in key_fields]
                where_clause = " AND ".join(where_parts)

                query = f"UPDATE `{table_name}` SET {set_clause} WHERE {where_clause}"
                # Параметры: сначала значения для SET, затем значения для WHERE
                params = list(new_row.values()) + [old_row[k] for k in key_fields]
                logger.debug(f"Executing UPDATE query {i+1}: {query} with params {params}")

                cursor.execute(query, params)

            cursor.close()
            logger.info(f"Successfully updated {len(updates)} rows in table '{table_name}'.")
        except sqlite3.Error as err:
            logger.error(f"Error updating  {err}")
            raise Exception(f"Error updating  {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during update_ {e}")
            raise

    def delete_data(self, deletions: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        """
        Удаляет строки из таблицы SQLite на основе ключевых полей.
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

            # WHERE часть
            where_parts = [f"`{k}` = ?" for k in key_fields]
            where_clause = " AND ".join(where_parts)
            query = f"DELETE FROM `{table_name}` WHERE {where_clause}"

            for i, del_row in enumerate(deletions):
                params = [del_row[k] for k in key_fields]
                logger.debug(f"Executing DELETE query {i+1}: {query} with params {params}")
                cursor.execute(query, params)

            cursor.close()
            logger.info(f"Successfully deleted {len(deletions)} rows from table '{table_name}'.")
        except sqlite3.Error as err:
            logger.error(f"Error deleting  {err}")
            raise Exception(f"Error deleting  {err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during delete_ {e}")
            raise
    # ---------------------------------------------

    def disconnect(self):
        try:
            if self.connection:
                self.connection.close()
                logger.info("SQLite connection closed.")
        except Exception as e:
            logger.error(f"An error occurred during disconnect: {e}")
            raise # Возбуждаем исключение дальше, если это критично


    def standard_formatting(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Стандартное форматирование данных после выборки из SQLite
        """
        try:
            logger.debug(f"Starting standard formatting for {len(data)} rows.")
            formatted_data = []
            # Регулярные выражения для проверки формата даты/времени и даты
            # Эти же паттерны, что и в CSV
            datetime_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
            date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

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
                    elif isinstance(value, (datetime, date)): # Если значение уже объект даты/времени
                        # Оставляем как есть, но можно привести к нужному формату строки, если нужно
                        # В текущем контексте оставляем объект
                        formatted_row[key] = value
                    elif isinstance(value, str): # Если значение строка, проверяем на дату/время
                        stripped_value = value.strip()

                        # Проверка на формат даты и времени: YYYY-MM-DD HH:MM:SS
                        if datetime_pattern.match(stripped_value):
                            try:
                                # Преобразуем строку в datetime объект
                                parsed_datetime = datetime.strptime(stripped_value, '%Y-%m-%d %H:%M:%S')
                                # Сохраняем как объект datetime
                                formatted_row[key] = parsed_datetime
                                continue  # Переходим к следующему значению
                            except ValueError:
                                pass  # Если формат не подошёл, продолжаем проверки

                        # Проверка на формат даты: YYYY-MM-DD
                        if date_pattern.match(stripped_value):
                            try:
                                # Преобразуем строку в date объект
                                parsed_date = date.fromisoformat(stripped_value)
                                # Сохраняем как объект date
                                formatted_row[key] = parsed_date
                                continue
                            except ValueError:
                                pass  # Если формат не подошёл, продолжаем проверки

                        # Попробуем определить числовые значения из строки
                        try:
                            # Проверяем, содержит ли строка точку (кандидат на float)
                            if '.' in stripped_value:
                                float_val = float(stripped_value)
                                # округляем до двух знаков
                                formatted_row[key] = round(float_val, 2)
                                continue
                            else:
                                # Целое число
                                formatted_row[key] = int(stripped_value)
                                continue
                        except ValueError:
                            # Если не число, оставляем как строку
                            formatted_row[key] = stripped_value
                    elif isinstance(value, float): # Если значение - число с плавающей точкой (уже не строка)
                        # Округляем до двух знаков после запятой
                        formatted_row[key] = round(value, 2)
                    else:
                        # Если значение не строка, не дата/время, не float, оставляем как есть
                        formatted_row[key] = value
                formatted_data.append(formatted_row)
            logger.debug(f"Standard formatting completed for {len(formatted_data)} rows.")
            return formatted_data
        except Exception as e:
            logger.error(f"An error occurred during standard_formatting: {e}")
            raise