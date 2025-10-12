# data_transfer.py
import importlib.util
from typing import Any, Dict, List, Tuple
from data_sources import DataSource, SQLDataSource, CSVDataSource, MySqlDataSource

# Импортируем функции форматирования
from data_sources.sql_source import standard_formatting as sql_formatting
from data_sources.mysql_source import standard_formatting as mysql_formatting
from data_sources.csv_source import standard_formatting as csv_formatting


# Основной класс переноса данных
class DataTransfer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.source_data = []
        self.destination_data = []
        self.formatted_source = []
        self.formatted_destination = []
        self.to_insert = []
        self.to_update = []
        self.to_delete = []

    def get_data_source(self, source_type: str, connection_params: Dict[str, Any]) -> DataSource:
        if source_type == "sql":
            return SQLDataSource(connection_params)
        elif source_type == "mysql":
            return MySqlDataSource(connection_params)
        elif source_type == "csv":
            return CSVDataSource(connection_params)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

    def fetch_data(self):
        # Получаем данные из источника
        source_config = self.config["source"]
        source = self.get_data_source(
            source_config["type"],
            source_config["connection_params"]
        )

        try:
            source.connect()
            self.source_data = source.fetch_data(
                source_config["query"],
                source_config.get("filters", {})
            )
        finally:
            source.disconnect()

        # Получаем данные из приемника
        dest_config = self.config["destination"]
        destination = self.get_data_source(
            dest_config["type"],
            dest_config["connection_params"]
        )

        try:
            destination.connect()
            # В простом случае - получаем все данные из таблицы
            query = f"SELECT * FROM {dest_config['table']}"
            self.destination_data = destination.fetch_data(query)
        finally:
            destination.disconnect()

    def format_data(self):
        # Приведение данных к общему формату с использованием стандартных функций
        source_type = self.config["source"]["type"]
        dest_type = self.config["destination"]["type"]

        # Форматирование исходных данных
        if source_type == "sql":
            self.formatted_source = sql_formatting(self.source_data)
        elif source_type == "mysql":
            self.formatted_source = mysql_formatting(self.source_data)
        elif source_type == "csv":
            self.formatted_source = csv_formatting(self.source_data)
        else:
            # Если форматирование не определено, просто копируем
            self.formatted_source = [dict(row) for row in self.source_data]

        # Форматирование данных приемника
        if dest_type == "sql":
            self.formatted_destination = sql_formatting(self.destination_data)
        elif dest_type == "mysql":
            self.formatted_destination = mysql_formatting(self.destination_data)
        elif dest_type == "csv":
            self.formatted_destination = csv_formatting(self.destination_data)
        else:
            # Если форматирование не определено, просто копируем
            self.formatted_destination = [dict(row) for row in self.destination_data]

    def transform_data(self):
        # Модификация данных после выборки
        transformation_config = self.config["transformation"]

        # Трансформация исходных данных
        if transformation_config.get("source_path"):
            transform_func = self.load_transform_function(transformation_config["source_path"])
            if transform_func:
                self.formatted_source = transform_func(self.formatted_source)

        # Трансформация данных приемника
        if transformation_config.get("destination_path"):
            transform_func = self.load_transform_function(transformation_config["destination_path"])
            if transform_func:
                self.formatted_destination = transform_func(self.formatted_destination)

    def load_transform_function(self, file_path: str):
        # Загружаем функцию трансформации из файла
        if not os.path.exists(file_path):
            return None

        spec = importlib.util.spec_from_file_location("transform_module", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Предполагаем, что в файле есть функция transform
        if hasattr(module, 'transform'):
            return module.transform
        return None

    def compare_data(self):
        # Сравнение данных
        key_fields = self.config["comparison"]["key_fields"]

        # Создаем словари для быстрого поиска
        source_dict = {self.get_key(row, key_fields): row for row in self.formatted_source}
        dest_dict = {self.get_key(row, key_fields): row for row in self.formatted_destination}

        # Определяем, что нужно вставить
        self.to_insert = []
        for key, row in source_dict.items():
            if key not in dest_dict:
                self.to_insert.append(row)

        # Определяем, что нужно обновить или удалить
        self.to_update = []
        self.to_delete = []

        for key, dest_row in dest_dict.items():
            if key in source_dict:
                # Сравниваем содержимое (упрощенно)
                source_row = source_dict[key]
                if not self.rows_equal(source_row, dest_row):
                    self.to_update.append({
                        "old": dest_row,
                        "new": source_row
                    })
            else:
                # Удалить из приемника
                self.to_delete.append(dest_row)

    def get_key(self, row: Dict[str, Any], key_fields: List[str]) -> str:
        # Создаем ключ из указанных полей
        key_parts = []
        for field in key_fields:
            key_parts.append(str(row.get(field, "")))
        return "|".join(key_parts)

    def rows_equal(self, row1: Dict[str, Any], row2: Dict[str, Any]) -> bool:
        # Проверяем равенство строк (упрощенно)
        for key in row1:
            if key not in row2:
                continue
            if row1[key] != row2[key]:
                return False
        for key in row2:
            if key not in row1:
                continue
            if row1[key] != row2[key]:
                return False
        return True

    def modify_data(self):
        # Модификация данных перед вставкой/обновлением/удалением
        transformation_config = self.config["transformation"]

        # Трансформация данных для вставки
        if transformation_config.get("destination_path"):
            transform_func = self.load_transform_function(transformation_config["destination_path"])
            if transform_func:
                self.to_insert = transform_func(self.to_insert)
                # Для обновления нужно трансформировать только "new" часть
                for update_item in self.to_update:
                    update_item["new"] = transform_func([update_item["new"]])[0]

    def execute_changes(self):
        # Выполняем изменения в приемнике
        dest_config = self.config["destination"]
        destination = self.get_data_source(
            dest_config["type"],
            dest_config["connection_params"]
        )

        try:
            destination.connect()

            # Вставляем новые записи
            for row in self.to_insert:
                placeholders = ", ".join(["%s" for _ in row])
                columns = ", ".join([f"`{k}`" for k in row.keys()])
                query = f"INSERT INTO `{dest_config['table']}` ({columns}) VALUES ({placeholders})"
                cursor = destination.connection.cursor()
                cursor.execute(query, list(row.values()))

            # Обновляем существующие записи
            for update_item in self.to_update:
                # Создаем SET часть запроса
                set_clause = ", ".join([f"`{k}` = %s" for k in update_item["new"].keys()])
                where_clause = " AND ".join([f"`{k}` = %s" for k in self.config["comparison"]["key_fields"]])
                query = f"UPDATE `{dest_config['table']}` SET {set_clause} WHERE {where_clause}"

                # Подготавливаем параметры
                values = list(update_item["new"].values())
                for key_field in self.config["comparison"]["key_fields"]:
                    values.append(update_item["old"][key_field])

                cursor = destination.connection.cursor()
                cursor.execute(query, values)

            # Удаляем записи
            for row in self.to_delete:
                where_clause = " AND ".join([f"`{k}` = %s" for k in self.config["comparison"]["key_fields"]])
                query = f"DELETE FROM `{dest_config['table']}` WHERE {where_clause}"

                cursor = destination.connection.cursor()
                values = [row[key] for key in self.config["comparison"]["key_fields"]]
                cursor.execute(query, values)

            destination.connection.commit()

        finally:
            destination.disconnect()

    def run(self):
        self.fetch_data()
        self.format_data()
        self.transform_data()
        self.compare_data()
        self.modify_data()
        self.execute_changes()