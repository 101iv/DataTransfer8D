# data_sources/csv_source.py
import csv
import os
from .base import DataSource
from typing import Any, Dict, List


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