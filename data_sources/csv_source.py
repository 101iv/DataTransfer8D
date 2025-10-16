# data_sources/csv_source.py
import csv
import os
import re
from datetime import datetime, date

from .base import DataSource
from typing import Any, Dict, List


class CSVDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.file_path = connection_params.get("query", "") or connection_params.get("path", "")
        self.delimiter = connection_params.get("delimiter", ",")
        self.newline = connection_params.get("newline", '') # Для Windows совместимости
        # --- Новое: внутреннее состояние данных ---
        self._current_data = None # Хранит текущее состояние данных в памяти, None если не загружено
        # ------------------------------------------

    def connect(self):
        # При connect() загружаем данные в кэш, если файл существует
        # Если файл не существует, кэш остаётся None до первого изменения
        if os.path.exists(self.file_path):
            with open(self.file_path, newline=self.newline, encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=self.delimiter)
                self._current_data = [dict(row) for row in reader]
        else:
            # Если файл не существует, устанавливаем кэш в пустой список
            # Это позволит корректно обрабатывать вставки в новый файл
            self._current_data = []
        # print(f"DEBUG: CSV loaded data, cache: {self._current_data}") # Отладка

    def fetch_data(self, query: str = "", params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        query: может быть пустой строкой или путем к файлу (если не задан в __init__)
        params: фильтры (опционально)
        """
        # Возвращаем текущее состояние кэша
        if self._current_data is None:
             # Если кэш не загружен (не подключались или файл был пуст/не существовал изначально),
             # и никто не вызвал connect, возвращаем пустой список.
             # Но connect должен был быть вызван перед fetch_data.
             # print("DEBUG: fetch_data called but cache is None. Returning empty list.")
             return []
        # Применяем фильтрацию, если она была передана
        if params and "filter" in params:
            filter_func = params["filter"]
            return [row for row in self._current_data if filter_func(row)]
        return self._current_data

    def get_schema(self) -> Dict[str, Any]:
        # Используем кэш, если он есть, иначе читаем файл напрямую
        if self._current_data and len(self._current_data) > 0:
            fieldnames = self._current_data[0].keys()
        else:
            # Если кэш пуст, читаем заголовки из файла, если он существует
            if os.path.exists(self.file_path):
                 with open(self.file_path, newline=self.newline, encoding='utf-8') as csvfile:
                     reader = csv.DictReader(csvfile, delimiter=self.delimiter)
                     fieldnames = reader.fieldnames
            else:
                fieldnames = []
        return {"columns": [{"name": name, "type": "TEXT"} for name in fieldnames]}

    # --- Вспомогательный метод для записи данных в файл ---
    def _write_data(self, data: List[Dict[str, Any]], path: str = None):
        """Вспомогательный метод для записи данных в CSV файл."""
        path_to_use = path if path else self.file_path
        if not data:
            # Если данные пустые, создаем файл с заголовками или очищаем его
            # Используем заголовки из кэша, если он был, или оставляем пустым
            fieldnames = []
            if self._current_data and len(self._current_data) > 0:
                 fieldnames = self._current_data[0].keys()
            with open(path_to_use, 'w', newline=self.newline, encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=self.delimiter)
                if fieldnames: # Записываем заголовки только если они есть
                    writer.writeheader()
            return

        # Определяем заголовки из первой строки данных
        fieldnames = data[0].keys()
        with open(path_to_use, 'w', newline=self.newline, encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=self.delimiter)
            writer.writeheader()
            writer.writerows(data)

    # --- Новые методы для INSERT, UPDATE, DELETE ---
    # Эти методы теперь работают с self._current_data и обновляют его
    def insert_data(self, data: List[Dict[str, Any]], table_name: str = None):
        """
        Добавляет новые строки в локальное представление данных (кэш).
        data: список словарей с данными для вставки
        table_name игнорируется для CSV.
        """
        # Обновляем локальное представление
        if self._current_data is None:
            # Если кэш не был загружен при connect, предполагаем пустой файл
            self._current_data = []
        self._current_data.extend(data)
        # print(f"DEBUG: Inserted data, cache now: {self._current_data}") # Отладка

    def update_data(self, updates: List[Dict[str, Any]], key_fields: List[str], table_name: str = None):
        """
        Обновляет строки в локальном представлении данных (кэш) на основе ключевых полей.
        updates: список словарей вида {"old": {...}, "new": {...}}
        key_fields: список ключевых полей для поиска
        table_name игнорируется для CSV.
        """
        if self._current_data is None:
            # Если кэш не был загружен, нечего обновлять
            print("Warning: Attempting to update CSV data, but no initial data was loaded or cache is empty.")
            return

        for update_item in updates:
            old_row = update_item["old"]
            new_row = update_item["new"]

            # Находим индекс строки для обновления
            for i, row in enumerate(self._current_data):
                # Преобразуем значения ключей к строке для сравнения
                if all(str(row[k]) == str(old_row[k]) for k in key_fields):
                    self._current_data[i] = new_row # Заменяем старую строку на новую
                    break # Предполагаем уникальность по ключу, выходим из поиска

        # print(f"DEBUG: Updated data, cache now: {self._current_data}") # Отладка

    def delete_data(self, deletions: List[Dict[str, Any]], key_fields: List[str], table_name: str = None):
        """
        Удаляет строки из локального представления данных (кэш) на основе ключевых полей.
        deletions: список строк для удаления (содержит ключевые поля)
        key_fields: список ключевых полей для поиска
        table_name игнорируется для CSV.
        """
        if self._current_data is None:
            # Если кэш не был загружен, нечего удалять
            print("Warning: Attempting to delete CSV data, but no initial data was loaded or cache is empty.")
            return

        # Фильтруем существующие данные, исключая строки для удаления
        updated_data = []
        for row in self._current_data: # Используем self._current_data
            # Проверяем, есть ли текущая строка в списке на удаление
            to_delete = False
            for del_row in deletions:
                # Преобразуем значения ключей к строке для сравнения
                if all(str(row[k]) == str(del_row[k]) for k in key_fields):
                    to_delete = True
                    break
            if not to_delete:
                updated_data.append(row)

        # Обновляем локальное представление
        self._current_data = updated_data
        # print(f"DEBUG: Deleted data, cache now: {self._current_data}") # Отладка
    # ---------------------------------------------

    def disconnect(self):
        # Сохраняем кэш в файл при отключении, если кэш не None
        # (то есть connect() был вызван)
        if self._current_data is not None:
            # print(f"DEBUG: Disconnecting, writing cache to file: {self._current_data}") # Отладка
            self._write_data(self._current_data, self.file_path)
            # Сбрасываем кэш
            self._current_data = None
        # Если self._current_data == None, это означает, что connect() не был вызван
        # или файл был пуст/не существовал и не было изменений.
        # В этом случае просто выходим, ничего не записывая (файл либо уже пуст/не существовал,
        # либо не было изменений для сохранения).

    def standard_formatting(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Стандартное форматирование данных после выборки из CSV
        """
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
        return formatted_data
