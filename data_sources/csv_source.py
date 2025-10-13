# data_sources/csv_source.py
import csv
import os
from .base import DataSource
from typing import Any, Dict, List


class CSVDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.file_path = connection_params.get("path", "") or connection_params.get("query", "")
        self.delimiter = connection_params.get("delimiter", ",")
        self.newline = connection_params.get("newline", '') # Для Windows совместимости
        # --- Новое: внутреннее состояние данных ---
        self._current_data = None # Хранит текущее состояние данных в памяти
        # ------------------------------------------

    def connect(self):
        # Загружаем данные при подключении (или обновляем, если файл изменился)
        # Или просто читаем при первом вызове fetch_data
        # Для простоты, данные загружаются при первом fetch_data
        # и кэшируются. Последующие fetch_data возвращают кэш.
        # Изменения (insert, update, delete) изменяют этот кэш.
        # disconnect не влияет на кэш.
        # reconnect (в смысле перечитывания файла) может обновить кэш.
        pass # Подключение для CSV - это подготовка, данные читаются при fetch_data

    def fetch_data(self, query: str = "", params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        query: может быть пустой строкой или путем к файлу (если не задан в __init__)
        params: фильтры (опционально)
        """
        path_to_use = query if query else self.file_path
        if not os.path.exists(path_to_use):
            # Если файл не существует, возвращаем пустой список и устанавливаем кэш
            print(f"Warning: CSV file {path_to_use} does not exist. Returning empty list.")
            self._current_data = []
            return []

        # Если кэш уже есть, возвращаем его (предполагаем, что никто не менял файл извне)
        if self._current_data is not None:
            # Применяем фильтрацию, если она была передана
            if params and "filter" in params:
                filter_func = params["filter"]
                return [row for row in self._current_data if filter_func(row)]
            return self._current_data

        # Если кэша нет, читаем файл и создаем кэш
        with open(path_to_use, newline=self.newline, encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=self.delimiter)
            rows = [dict(row) for row in reader]

            # Применяем фильтрацию если задана
            if params and "filter" in params:
                filter_func = params["filter"]
                rows = [row for row in rows if filter_func(row)]

        self._current_data = rows # Кэшируем данные
        return self._current_data

    def get_schema(self) -> Dict[str, Any]:
        path_to_use = self.file_path
        if not os.path.exists(path_to_use):
            return {"columns": []}

        with open(path_to_use, newline=self.newline, encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=self.delimiter)
            fieldnames = reader.fieldnames
            # Простая схема - только имена колонок
            return {"columns": [{"name": name, "type": "TEXT"} for name in fieldnames]}

    def disconnect(self):
        # Сохраняем кэш в файл при отключении, если были изменения?
        # Или сохранение происходит только при выполнении изменений?
        # Пока не сохраняем автоматически.
        pass

    # --- Вспомогательный метод для записи данных в файл ---
    def _write_data(self, data: List[Dict[str, Any]], path: str = None):
        """Вспомогательный метод для записи данных в CSV файл."""
        path_to_use = path if path else self.file_path
        if not data:
            # Если данные пустые, создаем файл с заголовками или очищаем его
            fieldnames = [] # Или используем заголовки из конфига или из кэша, если он есть
            # Попробуем использовать заголовки из текущего кэша, если он есть
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
        Вставляет новые строки в CSV файл (локальное представление).
        data: список словарей с данными для вставки
        table_name игнорируется для CSV.
        """
        # Обновляем локальное представление
        if self._current_data is None:
            # Если кэш не был загружен, предполагаем пустой файл
            self._current_data = []
        self._current_data.extend(data)
        # Записываем обновлённое состояние в файл
        self._write_data(self._current_data)

    def update_data(self, updates: List[Dict[str, Any]], key_fields: List[str], table_name: str = None):
        """
        Обновляет строки в CSV файле (локальное представление) на основе ключевых полей.
        updates: список словарей вида {"old": {...}, "new": {...}}
        key_fields: список ключевых полей для поиска
        table_name игнорируется для CSV.
        """
        if self._current_data is None:
            # Если кэш не был загружен, нечего обновлять
            print("Warning: Attempting to update CSV data, but no initial data was loaded.")
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

        # Записываем обновлённое состояние в файл
        self._write_data(self._current_data)

    def delete_data(self, deletions: List[Dict[str, Any]], key_fields: List[str], table_name: str = None):
        """
        Удаляет строки из CSV файла (локальное представление) на основе ключевых полей.
        deletions: список строк для удаления (содержит ключевые поля)
        key_fields: список ключевых полей для поиска
        table_name игнорируется для CSV.
        """
        if self._current_data is None:
            # Если кэш не был загружен, нечего удалять
            print("Warning: Attempting to delete CSV data, but no initial data was loaded.")
            return

        # Фильтруем существующие данные, исключая строки для удаления
        updated_data = []
        for row in self._current_data:
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
        # Записываем обновлённое состояние в файл
        self._write_data(self._current_data)
    # ---------------------------------------------


def standard_formatting(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Стандартное форматирование данных после выборки из CSV
    """
    formatted_data = []
    for row in data:
        formatted_row = {}
        for key, value in row.items():
            # Приведение типов данных
            if isinstance(value, str):
                # Попробуем определить числовые значения
                try:
                    if '.' in value:
                        formatted_row[key] = float(value)
                    else:
                        formatted_row[key] = int(value)
                except ValueError:
                    # Если не число, оставляем как строку
                    formatted_row[key] = value.strip()
            else:
                formatted_row[key] = value
        formatted_data.append(formatted_row)
    return formatted_data
