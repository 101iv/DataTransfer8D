# connectors/xlsx_source.py
from .base import DataSource
from typing import Any, Dict, List
import openpyxl
from openpyxl.utils import get_column_letter
import os


class XlsxDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        # Ожидаем, что connection_params будет содержать 'file_path' - путь к .xlsx файлу
        self.file_path = connection_params.get("file_path")
        if not self.file_path:
            raise ValueError("Connection parameter 'file_path' is required for Excel file.")
        if not self.file_path.lower().endswith('.xlsx'):
            raise ValueError("File must have .xlsx extension.")

        # Сохраняем путь, но соединение устанавливается при вызове connect()
        # self.file_path = file_path # ОШИБКА: file_path не определена, должно быть self.file_path
        self._is_read_only = connection_params.get("read_only", True)  # Добавим флаг для режима чтения

    def connect(self):
        try:
            if self._is_read_only:
                # load_workbook в режиме read_only быстрее и потребляет меньше памяти
                self.workbook = openpyxl.load_workbook(self.file_path, read_only=True)
            else:
                # Для записи/редактирования
                self.workbook = openpyxl.load_workbook(self.file_path)
        except FileNotFoundError:
            raise Exception(f"Excel file not found: {self.file_path}")
        except Exception as err:
            raise Exception(f"Excel connection failed: {err}")

    def fetch_data(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Извлекает данные из листа Excel.
        query: имя листа (например, 'Sheet1')
        params: не используется для openpyxl
        """
        if not self.workbook:
            raise Exception("Workbook not loaded. Call connect() first.")

        if params:
            print("Warning: params are not used in XlsxDataSource.fetch_data")

        try:
            worksheet = self.workbook[query]
        except KeyError:
            raise Exception(f"Worksheet '{query}' not found in the workbook.")

        rows = worksheet.iter_rows(values_only=True)
        data = list(rows)

        if not data:  # ОШИБКА: отсутствовало условие
            return []

        # Предполагаем, что первая строка - заголовки
        headers = data[0]
        # Пропускаем заголовки и формируем словари
        result = []
        for row in data[1:]:
            # Пропускаем пустые строки (если все значения None)
            if any(cell is not None for cell in row):
                result.append(dict(zip(headers, row)))
        return result

    def build_select_query(self, table_name: str, fields: List[str] = None) -> str:
        """
        Для XlsxDataSource, table_name - это имя листа.
        Возвращаем просто имя листа, так как SQL-запросы не используются.
        """
        # fields игнорируются, так как openpyxl не использует SQL.
        # В fetch_data нужно будет отфильтровать вручную, если нужно.
        return table_name

    def get_schema(self) -> Dict[str, Any]:
        """
        Возвращает информацию о листах и первых строках (предполагаем заголовки).
        """
        if not self.workbook:
            raise Exception("Workbook not loaded. Call connect() first.")

        schema = {}
        for sheet_name in self.workbook.sheetnames:
            worksheet = self.workbook[sheet_name]

            # Получаем первую строку (заголовки)
            headers = []
            for col_idx, cell in enumerate(worksheet[1], start=1):  # worksheet[1] - первая строка
                # Имя колонки может быть None, если ячейка пуста
                header_name = cell.value if cell.value is not None else f"Column_{get_column_letter(col_idx)}"
                headers.append(header_name)

            # Предполагаем, что тип данных - это тип значения в первой строке данных (если есть)
            # Это грубое приближение, т.к. типы могут меняться в столбце
            schema[sheet_name] = []
            for header in headers:
                # Так как Excel не хранит типы строго, мы можем только зафиксировать имя
                # и, возможно, тип первого значения в данных (строка 2)
                # Пока оставим тип как строку, можно улучшить
                schema[sheet_name].append({
                    "name": header,
                    "type": "unknown",  # openpyxl не предоставляет строгий тип колонки
                    "not_null": False,  # Excel не имеет ограничений NOT NULL
                    "default": None,
                    "extra": "",
                    "primary_key": False  # Excel не имеет первичных ключей
                })

        return schema

    # --- Новые методы для INSERT, UPDATE, DELETE ---
    # ВНИМАНИЕ: Эти операции требуют открытия файла в режиме записи (read_only=False).
    # Их выполнение может быть сложнее, чем в базах данных.
    # Также файл не должен быть открыт вручную в Excel во время операций.
    def insert_data(self, data: List[Dict[str, Any]], table_name: str):
        """
        Вставляет новые строки в лист Excel.
        data: список словарей с данными. Ключи должны соответствовать заголовкам в Excel.
        table_name: имя листа.
        """
        if self._is_read_only:
            raise Exception("Cannot insert data: workbook opened in read-only mode.")

        if not self.workbook:
            raise Exception("Workbook not loaded. Call connect() first.")

        if not data:  # ОШИБКА: отсутствовало условие
            return  # Нечего вставлять

        try:
            worksheet = self.workbook[table_name]
        except KeyError:
            raise Exception(f"Worksheet '{table_name}' not found in the workbook.")

        # Получаем заголовки из Excel (предполагаем, что они в строке 1)
        headers = [cell.value for cell in worksheet[1]]

        # Проверяем, что все ключи в data присутствуют в заголовках
        for row_data in data:  # ОШИБКА: отсутствовало имя переменной в цикле
            for key in row_data.keys():
                if key not in headers:
                    raise ValueError(f"Column '{key}' not found in worksheet '{table_name}' headers.")

        # Найти следующую пустую строку для вставки
        next_row_idx = worksheet.max_row + 1

        for row_data in data:
            # Создаем список значений в том же порядке, что и заголовки
            row_values = [row_data.get(header, None) for header in headers]
            for col_idx, value in enumerate(row_values, start=1):
                worksheet.cell(row=next_row_idx, column=col_idx, value=value)
            next_row_idx += 1

    def update_data(self, updates: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        """
        Обновляет строки в листе Excel на основе ключевых полей.
        Это требует поиска соответствующей строки по key_fields.
        updates: список словарей вида {"old": {...}, "new": {...}}
        key_fields: список ключевых полей для поиска.
        table_name: имя листа.
        """
        if self._is_read_only:
            raise Exception("Cannot update data: workbook opened in read-only mode.")

        if not self.workbook:
            raise Exception("Workbook not loaded. Call connect() first.")

        if not updates:
            return  # Нечего обновлять

        try:
            worksheet = self.workbook[table_name]
        except KeyError:
            raise Exception(f"Worksheet '{table_name}' not found in the workbook.")

        headers = [cell.value for cell in worksheet[1]]

        # Проверяем, что все key_fields присутствуют в заголовках
        for kf in key_fields:
            if kf not in headers:
                raise ValueError(f"Key field '{kf}' not found in worksheet '{table_name}' headers.")

        # Проходим по всем строкам данных (начиная с 2, т.к. 1 - заголовки)
        for row_idx in range(2, worksheet.max_row + 1):
            # Создаем словарь текущей строки
            current_row_dict = {}
            for col_idx, header in enumerate(headers, start=1):
                current_row_dict[header] = worksheet.cell(row=row_idx, column=col_idx).value

            # Ищем совпадение по key_fields в списке updates
            for update_item in updates:
                old_row = update_item["old"]
                new_row = update_item["new"]

                # Проверяем, совпадают ли ключевые поля
                match = all(current_row_dict.get(kf) == old_row.get(kf) for kf in key_fields)
                if match:
                    # Обновляем значения в строке
                    for key, value in new_row.items():
                        if key in headers:
                            col_idx = headers.index(key) + 1  # Индексация столбцов начинается с 1
                            worksheet.cell(row=row_idx, column=col_idx, value=value)
                    # Если обновление найдено и выполнено, выходим из внутреннего цикла
                    # (если в updates могут быть дубликаты для одной строки - решать вам)
                    break  # Прерываем цикл по updates для этой строки

    def delete_data(self, deletions: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        """
        Удаляет строки из листа Excel на основе ключевых полей.
        В openpyxl удаление строк сдвигает остальные.
        deletions: список строк для удаления (их ключевые поля).
        key_fields: список ключевых полей для поиска.
        table_name: имя листа.
        """
        if self._is_read_only:
            raise Exception("Cannot delete data: workbook opened in read-only mode.")

        if not self.workbook:
            raise Exception("Workbook not loaded. Call connect() first.")

        if not deletions:
            return  # Нечего удалять

        try:
            worksheet = self.workbook[table_name]
        except KeyError:
            raise Exception(f"Worksheet '{table_name}' not found in the workbook.")

        headers = [cell.value for cell in worksheet[1]]

        # Проверяем, что все key_fields присутствуют в заголовках
        for kf in key_fields:
            if kf not in headers:
                raise ValueError(f"Key field '{kf}' not found in worksheet '{table_name}' headers.")

        # Собираем индексы строк для удаления (с конца, чтобы индексы не сбивались)
        rows_to_delete = []
        for row_idx in range(2, worksheet.max_row + 1):
            current_row_dict = {}
            for col_idx, header in enumerate(headers, start=1):
                current_row_dict[header] = worksheet.cell(row=row_idx, column=col_idx).value

            for del_row in deletions:
                match = all(current_row_dict.get(kf) == del_row.get(kf) for kf in key_fields)
                if match:
                    rows_to_delete.append(row_idx)
                    break  # Нашли совпадение для этой строки, идем к следующей

        # Сортируем индексы в обратном порядке
        rows_to_delete.sort(reverse=True)

        # Удаляем строки
        for row_idx in rows_to_delete:
            worksheet.delete_rows(row_idx, 1)  # Удаляем 1 строку, начиная с row_idx

    # ---------------------------------------------

    def disconnect(self):
        if self.workbook:
            # Если файл открывался в режиме записи, нужно его сохранить
            if not self._is_read_only:
                try:
                    self.workbook.save(self.file_path)
                    print(f"Workbook saved to {self.file_path}")
                except PermissionError:
                    raise Exception(
                        f"Could not save file: {self.file_path} might be open in Excel or lack write permissions.")
            self.workbook.close()
            self.workbook = None

    def standard_formatting(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Стандартное форматирование данных после выборки из Excel.
        openpyxl обычно возвращает правильные типы Python (str, int, float, datetime, bool, None).
        """
        # В большинстве случаев, openpyxl уже возвращает нужные типы.
        # Можно добавить логику, если требуются специфичные преобразования.
        # Пока возвращаем как есть.
        return data