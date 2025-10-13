# data_sources/csv_source.py
import csv
import os
from .base import DataSource
from typing import Any, Dict, List


class CSVDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        # Основной путь к файлу - из ключа 'path' или 'query' (для совместимости с fetch_data в data_transfer)
        self.file_path = connection_params.get("path", "") or connection_params.get("query", "")
        self.delimiter = connection_params.get("delimiter", ",")
        self.newline = connection_params.get("newline", '') # Для Windows совместимости

    def connect(self):
        # Проверяем, существует ли файл при подключении (опционально, можно создать, если нет)
        # Если файл не существует, будем считать, что он пустой
        # или создадим его с заголовками, если вставка будет первой.
        pass # Подключение для CSV - это просто проверка пути или подготовка

    def fetch_data(self, query: str = "", params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        query: может быть пустой строкой или путем к файлу (если не задан в __init__)
        params: фильтры (опционально)
        """
        path_to_use = query if query else self.file_path
        if not os.path.exists(path_to_use):
            # Если файл не существует, возвращаем пустой список
            print(f"Warning: CSV file {path_to_use} does not exist. Returning empty list.")
            return []

        with open(path_to_use, newline=self.newline, encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=self.delimiter)
            rows = [dict(row) for row in reader]

            # Применяем фильтрацию если задана
            if params and "filter" in params:
                filter_func = params["filter"]
                rows = [row for row in rows if filter_func(row)]

            return rows

    def get_schema(self) -> Dict[str, Any]:
        if not os.path.exists(self.file_path):
            return {"columns": []}

        with open(self.file_path, newline=self.newline, encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=self.delimiter)
            fieldnames = reader.fieldnames
            # Простая схема - только имена колонок
            return {"columns": [{"name": name, "type": "TEXT"} for name in fieldnames]}

    def disconnect(self):
        pass  # Для CSV файлов нет необходимости в отключении

    # --- Новые методы для INSERT, UPDATE, DELETE ---

    def _write_data(self, data: List[Dict[str, Any]], path: str = None):
        """Вспомогательный метод для записи данных в CSV файл."""
        path_to_use = path if path else self.file_path
        if not data:
            # Если данные пустые, создаем файл с заголовками или очищаем его
            fieldnames = [] # Или используем заголовки из конфига
            with open(path_to_use, 'w', newline=self.newline, encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=self.delimiter)
                writer.writeheader()
            return

        # Определяем заголовки из первой строки данных
        fieldnames = data[0].keys()
        with open(path_to_use, 'w', newline=self.newline, encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=self.delimiter)
            writer.writeheader()
            writer.writerows(data)

    def insert_data(self, data: List[Dict[str, Any]], table_name: str = None):
        """
        Вставляет новые строки в CSV файл.
        table_name игнорируется для CSV.
        """
        existing_data = self.fetch_data() # Читаем текущие данные
        updated_data = existing_data + data # Добавляем новые
        self._write_data(updated_data) # Перезаписываем файл

    def update_data(self, updates: List[Dict[str, Any]], key_fields: List[str], table_name: str = None):
        """
        Обновляет строки в CSV файле на основе ключевых полей.
        updates: список словарей вида {"old": {...}, "new": {...}}
        key_fields: список ключевых полей для поиска
        table_name игнорируется для CSV.
        """
        existing_data = self.fetch_data() # Читаем текущие данные

        for update_item in updates:
            old_row = update_item["old"]
            new_row = update_item["new"]

            # Находим индекс строки для обновления
            for i, row in enumerate(existing_data):
                is_match = all(row[k] == old_row[k] for k in key_fields)
                if is_match:
                    existing_data[i] = new_row # Заменяем старую строку на новую
                    break # Предполагаем уникальность по ключу, выходим из поиска

        self._write_data(existing_data) # Перезаписываем файл

    def delete_data(self, deletions: List[Dict[str, Any]], key_fields: List[str], table_name: str = None):
        """
        Удаляет строки из CSV файла на основе ключевых полей.
        deletions: список строк для удаления
        key_fields: список ключевых полей для поиска
        table_name игнорируется для CSV.
        """
        existing_data = self.fetch_data() # Читаем текущие данные

        # Фильтруем существующие данные, исключая строки для удаления
        updated_data = []
        for row in existing_data:
            # Проверяем, есть ли текущая строка в списке на удаление
            to_delete = False
            for del_row in deletions:
                if all(row[k] == del_row[k] for k in key_fields):
                    to_delete = True
                    break
            if not to_delete:
                updated_data.append(row)

        self._write_data(updated_data) # Перезаписываем файл

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
