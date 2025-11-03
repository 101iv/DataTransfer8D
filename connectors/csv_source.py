# connectors/csv_source.py
import csv
import os
import re
from datetime import datetime, date
import logging

from .base import DataSource
from typing import Any, Dict, List

"""не определяет автоматом ключевые поля"""

# Настройка логирования для этого модуля
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)  # Создаем логгер для этого файла

class CSVDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.file_path = connection_params.get("query", "") or connection_params.get("path", "")
        self.delimiter = connection_params.get("delimiter", ",")
        self.newline = connection_params.get("newline", '') # Для Windows совместимости
        # --- Новое: внутреннее состояние данных ---
        self._current_data = None # Хранит текущее состояние данных в памяти, None если не загружено
        logger.debug(f"Initialized CSVDataSource with file_path: {self.file_path}, delimiter: '{self.delimiter}'")
        # ------------------------------------------

    def connect(self):
        try:
            logger.info(f"Attempting to load CSV data from: {self.file_path}")
            # При connect() загружаем данные в кэш, если файл существует
            # Если файл не существует, кэш остаётся None до первого изменения
            if os.path.exists(self.file_path):
                logger.debug(f"File {self.file_path} exists, reading data.")
                with open(self.file_path, newline=self.newline, encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile, delimiter=self.delimiter)
                    self._current_data = [dict(row) for row in reader]
                logger.info(f"Successfully loaded {len(self._current_data)} rows from {self.file_path}.")
            else:
                logger.warning(f"File {self.file_path} does not exist. Initializing cache as empty list.")
                # Если файл не существует, устанавливаем кэш в пустой список
                # Это позволит корректно обрабатывать вставки в новый файл
                self._current_data = []
        except FileNotFoundError:
            logger.error(f"File not found during connect: {self.file_path}")
            self._current_data = []
        except Exception as e:
            logger.error(f"An unexpected error occurred during connect for CSV: {e}")
            raise

    def fetch_data(self, query: str = "", params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        query: может быть пустой строкой или путем к файлу (если не задан в __init__)
        params: фильтры (опционально)
        """
        try:
            logger.debug(f"Fetching data, cache length: {len(self._current_data) if self._current_data is not None else 'None'}")
            # Возвращаем текущее состояние кэша
            if self._current_data is None:
                 # Если кэш не загружен (не подключались или файл был пуст/не существовал изначально),
                 # и никто не вызвал connect, возвращаем пустой список.
                 # Но connect должен был быть вызван перед fetch_data.
                 logger.warning("fetch_data called but cache is None. Returning empty list.")
                 return []
            # Применяем фильтрацию, если она была передана
            if params and "filter" in params:
                filter_func = params["filter"]
                logger.debug("Applying filter to fetched data.")
                filtered_data = [row for row in self._current_data if filter_func(row)]
                logger.info(f"Fetched {len(filtered_data)} rows after applying filter.")
                return filtered_data
            logger.info(f"Fetched {len(self._current_data)} rows from cache.")
            return self._current_data
        except Exception as e:
            logger.error(f"An error occurred during fetch_data: {e}")
            raise

    def get_schema(self) -> Dict[str, Any]:
        try:
            logger.debug("Fetching schema for CSV.")
            # Используем кэш, если он есть, иначе читаем файл напрямую
            if self._current_data and len(self._current_data) > 0:
                fieldnames = self._current_data[0].keys()
                logger.debug(f"Schema inferred from cache: {list(fieldnames)}")
            else:
                # Если кэш пуст, читаем заголовки из файла, если он существует
                if os.path.exists(self.file_path):
                    logger.debug(f"Cache is empty, reading headers from file: {self.file_path}")
                    with open(self.file_path, newline=self.newline, encoding='utf-8') as csvfile:
                        reader = csv.DictReader(csvfile, delimiter=self.delimiter)
                        fieldnames = reader.fieldnames
                    logger.debug(f"Schema read from file: {fieldnames}")
                else:
                    logger.warning(f"File {self.file_path} does not exist, schema will be empty.")
                    fieldnames = []
            schema = {"columns": [{"name": name, "type": "TEXT"} for name in fieldnames]}
            logger.info(f"Schema fetched with {len(fieldnames)} columns.")
            return schema
        except Exception as e:
            logger.error(f"An error occurred during get_schema: {e}")
            raise

    # --- Вспомогательный метод для записи данных в файл ---
    def _write_data(self, data: List[Dict[str, Any]], path: str = None):
        """Вспомогательный метод для записи данных в CSV файл."""
        try:
            path_to_use = path if path else self.file_path
            logger.debug(f"Writing data to file: {path_to_use}. Data length: {len(data)}")
            if not data:
                logger.debug("Data list is empty, creating file with headers or clearing it.")
                # Если данные пустые, создаем файл с заголовками или очищаем его
                # Используем заголовки из кэша, если он был, или оставляем пустым
                fieldnames = []
                if self._current_data and len(self._current_data) > 0:
                     fieldnames = self._current_data[0].keys()
                with open(path_to_use, 'w', newline=self.newline, encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=self.delimiter)
                    if fieldnames: # Записываем заголовки только если они есть
                        logger.debug(f"Writing headers: {list(fieldnames)}")
                        writer.writeheader()
                logger.info(f"Created/cleared file {path_to_use} (possibly with headers).")
                return

            # Определяем заголовки из первой строки данных
            fieldnames = data[0].keys()
            logger.debug(f"Writing data with headers: {list(fieldnames)}")
            with open(path_to_use, 'w', newline=self.newline, encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=self.delimiter)
                writer.writeheader()
                writer.writerows(data)
            logger.info(f"Successfully wrote {len(data)} rows to file {path_to_use}.")
        except Exception as e:
            logger.error(f"An error occurred while writing data to file {path_to_use}: {e}")
            raise

    # --- Новые методы для INSERT, UPDATE, DELETE ---
    # Эти методы теперь работают с self._current_data и обновляют его
    def insert_data(self, data: List[Dict[str, Any]], table_name: str = None):
        """
        Добавляет новые строки в локальное представление данных (кэш).
        data: список словарей с данными для вставки
        table_name игнорируется для CSV.
        """
        try:
            logger.info(f"Attempting to insert {len(data)} rows into CSV cache.")
            # Обновляем локальное представление
            if self._current_data is None:
                # Если кэш не был загружен при connect, предполагаем пустой файл
                logger.debug("Cache was not loaded, initializing as empty list.")
                self._current_data = []
            self._current_data.extend(data)
            logger.info(f"Successfully inserted {len(data)} rows. Cache now has {len(self._current_data)} rows.")
        except Exception as e:
            logger.error(f"An error occurred during insert_data: {e}")
            raise

    def update_data(self, updates: List[Dict[str, Any]], key_fields: List[str], table_name: str = None):
        """
        Обновляет строки в локальном представлении данных (кэш) на основе ключевых полей.
        updates: список словарей вида {"old": {...}, "new": {...}}
        key_fields: список ключевых полей для поиска
        table_name игнорируется для CSV.
        """
        try:
            logger.info(f"Attempting to update {len(updates)} rows in CSV cache using key fields: {key_fields}.")
            if self._current_data is None:
                # Если кэш не был загружен, нечего обновлять
                logger.warning("Attempting to update CSV data, but no initial data was loaded or cache is empty.")
                return

            updated_count = 0
            for update_item in updates:
                old_row = update_item["old"]
                new_row = update_item["new"]

                # Находим индекс строки для обновления
                for i, row in enumerate(self._current_data):
                    # Преобразуем значения ключей к строке для сравнения
                    if all(str(row[k]) == str(old_row[k]) for k in key_fields):
                        self._current_data[i] = new_row # Заменяем старую строку на новую
                        updated_count += 1
                        logger.debug(f"Updated row at index {i} using keys {key_fields}. New values: {new_row}")
                        break # Предполагаем уникальность по ключу, выходим из поиска

            logger.info(f"Successfully updated {updated_count} rows out of {len(updates)} requested.")
        except Exception as e:
            logger.error(f"An error occurred during update_data: {e}")
            raise

    def delete_data(self, deletions: List[Dict[str, Any]], key_fields: List[str], table_name: str = None):
        """
        Удаляет строки из локального представления данных (кэш) на основе ключевых полей.
        deletions: список строк для удаления (содержит ключевые поля)
        key_fields: список ключевых полей для поиска
        table_name игнорируется для CSV.
        """
        try:
            logger.info(f"Attempting to delete {len(deletions)} rows from CSV cache using key fields: {key_fields}.")
            if self._current_data is None:
                # Если кэш не был загружен, нечего удалять
                logger.warning("Attempting to delete CSV data, but no initial data was loaded or cache is empty.")
                return

            initial_count = len(self._current_data)
            # Фильтруем существующие данные, исключая строки для удаления
            updated_data = []
            deleted_count = 0
            for row in self._current_data: # Используем self._current_data
                # Проверяем, есть ли текущая строка в списке на удаление
                to_delete = False
                for del_row in deletions:
                    # Преобразуем значения ключей к строке для сравнения
                    if all(str(row[k]) == str(del_row[k]) for k in key_fields):
                        to_delete = True
                        deleted_count += 1
                        logger.debug(f"Marking row for deletion based on keys {key_fields}: {row}")
                        break
                if not to_delete:
                    updated_data.append(row)

            # Обновляем локальное представление
            self._current_data = updated_data
            final_count = len(self._current_data)
            logger.info(f"Successfully deleted {deleted_count} rows. Cache size changed from {initial_count} to {final_count}.")
        except Exception as e:
            logger.error(f"An error occurred during delete_data: {e}")
            raise
    # ---------------------------------------------

    def disconnect(self):
        try:
            # Сохраняем кэш в файл при отключении, если кэш не None
            # (то есть connect() был вызван)
            if self._current_data is not None:
                logger.info(f"Disconnecting, writing cache ({len(self._current_data)} rows) to file: {self.file_path}")
                self._write_data(self._current_data, self.file_path)
                # Сбрасываем кэш
                self._current_data = None
                logger.info("CSV connection closed and data saved.")
            else:
                # Если self._current_data == None, это означает, что connect() не был вызван
                # или файл был пуст/не существовал и не было изменений.
                # В этом случае просто выходим, ничего не записывая (файл либо уже пуст/не существовал,
                # либо не было изменений для сохранения).
                logger.info("Disconnecting, but no data was loaded or modified, skipping save.")
        except Exception as e:
            logger.error(f"An error occurred during disconnect: {e}")
            raise # Возбуждаем исключение дальше, если это критично для процесса

    def standard_formatting(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Стандартное форматирование данных после выборки из CSV
        """
        try:
            logger.debug(f"Starting standard formatting for {len(data)} rows.")
            formatted_data = []
            # Регулярные выражения для проверки формата даты/времени и даты
            datetime_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
            date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

            for row in data:
                formatted_row = {}
                for key, value in row.items():
                    if isinstance(value, str):
                        stripped_value = value.strip()

                        # Проверка на формат даты и времени: YYYY-MM-DD HH:MM:SS
                        if datetime_pattern.match(stripped_value):
                            try:
                                formatted_row[key] = datetime.strptime(stripped_value, '%Y-%m-%d %H:%M:%S')
                                continue  # Переходим к следующему значению
                            except ValueError:
                                pass  # Если формат не подошёл, продолжаем проверки

                        # Проверка на формат даты: YYYY-MM-DD
                        if date_pattern.match(stripped_value):
                            try:
                                formatted_row[key] = date.fromisoformat(stripped_value)
                                # Альтернатива: datetime.strptime(stripped_value, '%Y-%m-%d').date()
                                continue
                            except ValueError:
                                pass  # Если формат не подошёл, продолжаем проверки

                        # Попробуем определить числовые значения
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
                    else:
                        # Если значение не строка, оставляем как есть
                        formatted_row[key] = value
                formatted_data.append(formatted_row)
            logger.debug(f"Standard formatting completed for {len(formatted_data)} rows.")
            return formatted_data
        except Exception as e:
            logger.error(f"An error occurred during standard_formatting: {e}")
            raise