# data_transfer.py
import importlib.util
import logging # Добавляем импорт модуля logging
import os # Добавлено для проверки существования файла в load_transform_function
from typing import Any, Dict, List, Tuple
from data_sources import DataSource, SQLDataSource, CSVDataSource, MySqlDataSource

# Импортируем функции форматирования
from data_sources.sql_source import standard_formatting as sql_formatting
from data_sources.mysql_source import standard_formatting as mysql_formatting
from data_sources.csv_source import standard_formatting as csv_formatting

# Настройка логирования для этого модуля
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Создаем логгер для этого файла

# Основной класс переноса данных
class DataTransfer:
    def __init__(self, config: Dict[str, Any]):
        logger.info("Инициализация DataTransfer")
        self.config = config
        self.source_data = []
        self.destination_data = []
        self.formatted_source = []
        self.formatted_destination = []
        self.to_insert = []
        self.to_update = []
        self.to_delete = []

    def get_data_source(self, source_type: str, connection_params: Dict[str, Any]) -> DataSource:
        logger.debug(f"Получение источника данных типа: {source_type}")
        if source_type == "sql":
            return SQLDataSource(connection_params)
        elif source_type == "mysql":
            return MySqlDataSource(connection_params)
        elif source_type == "csv":
            return CSVDataSource(connection_params)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

    def fetch_data(self):
        logger.info("Начало загрузки данных")
        # Получаем данные из источника
        source_config = self.config["source"]
        source = self.get_data_source(
            source_config["type"],
            source_config["connection_params"]
        )
        try:
            logger.debug("Подключение к источнику...")
            source.connect()
            logger.debug("Загрузка данных из источника...")
            self.source_data = source.fetch_data(
                source_config["query"],
                source_config.get("filters", {})
            )
            logger.info(f"Загружено {len(self.source_data)} записей из источника.")
        finally:
            logger.debug("Отключение от источника...")
            source.disconnect()

        # Получаем данные из приемника
        dest_config = self.config["destination"]
        destination = self.get_data_source(
            dest_config["type"],
            dest_config["connection_params"]
        )
        try:
            logger.debug("Подключение к приемнику...")
            destination.connect()

            query_for_dest = dest_config.get("query", "")
            if not query_for_dest and dest_config["type"] == "csv":
                query_for_dest = dest_config["connection_params"].get("path", "")
            logger.debug(f"Выполнение запроса к приемнику: {query_for_dest}")
            self.destination_data = destination.fetch_data(query_for_dest)
            logger.info(f"Загружено {len(self.destination_data)} записей из приемника.")
        except KeyError as e:
             logger.error(f"Ключ отсутствует в конфигурации destination: {e}")
             raise # Передаем ошибку выше
        finally:
            logger.debug("Отключение от приемника...")
            destination.disconnect()
        logger.info("Завершена загрузка данных")

    def format_data(self):
        logger.info("Начало форматирования данных")
        # Приведение данных к общему формату с использованием стандартных функций
        source_type = self.config["source"]["type"]
        dest_type = self.config["destination"]["type"]
        logger.debug(f"Тип источника: {source_type}, Тип приемника: {dest_type}")

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
        logger.info(f"Форматирование исходных данных завершено. Обработано {len(self.formatted_source)} записей.")

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
        logger.info(f"Форматирование данных приемника завершено. Обработано {len(self.formatted_destination)} записей.")
        logger.info("Форматирование данных завершено")

    def transform_data(self):
        logger.info("Начало трансформации данных")
        # Модификация данных после выборки
        transformation_config = self.config["transformation"]
        logger.debug(f"Конфигурация трансформации: {transformation_config}")

        # Трансформация исходных данных
        if transformation_config.get("source_path"):
            logger.debug(f"Загрузка трансформации для источника из: {transformation_config['source_path']}")
            transform_func = self.load_transform_function(transformation_config["source_path"])
            if transform_func:
                logger.debug("Функция трансформации источника загружена, применяем...")
                self.formatted_source = transform_func(self.formatted_source)
                logger.info(f"Трансформация источника применена. Результат: {len(self.formatted_source)} записей.")
            else:
                logger.warning(f"Функция трансформации для источника не найдена в {transformation_config['source_path']}")

        # Трансформация данных приемника
        if transformation_config.get("destination_path"):
            logger.debug(f"Загрузка трансформации для приемника из: {transformation_config['destination_path']}")
            transform_func = self.load_transform_function(transformation_config["destination_path"])
            if transform_func:
                logger.debug("Функция трансформации приемника загружена, применяем...")
                self.formatted_destination = transform_func(self.formatted_destination)
                logger.info(f"Трансформация приемника применена. Результат: {len(self.formatted_destination)} записей.")
            else:
                logger.warning(f"Функция трансформации для приемника не найдена в {transformation_config['destination_path']}")
        logger.info("Трансформация данных завершена")

    def load_transform_function(self, file_path: str):
        # Загружаем функцию трансформации из файла
        logger.debug(f"Попытка загрузки функции трансформации из {file_path}")
        if not os.path.exists(file_path):
            logger.error(f"Файл трансформации не найден: {file_path}")
            return None
        try:
            spec = importlib.util.spec_from_file_location("transform_module", file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Предполагаем, что в файле есть функция transform
            if hasattr(module, 'transform'):
                logger.debug(f"Функция 'transform' найдена в {file_path}")
                return module.transform
            else:
                logger.warning(f"Функция 'transform' не найдена в {file_path}")
                return None
        except Exception as e:
            logger.error(f"Ошибка при загрузке трансформации из {file_path}: {e}")
            return None

    def compare_data(self):
        logger.info("Начало сравнения данных")
        key_fields = self.config["comparison"]["key_fields"]
        logger.debug(f"Поля для сравнения (ключи): {key_fields}")

        # Создаем словари для быстрого поиска
        logger.debug("Создание словаря для исходных данных...")
        source_dict = {self.get_key(row, key_fields): row for row in self.formatted_source}
        logger.debug("Создание словаря для данных приемника...")
        dest_dict = {self.get_key(row, key_fields): row for row in self.formatted_destination}

        # Определяем, что нужно вставить
        logger.debug("Определение записей для вставки...")
        self.to_insert = []
        for key, row in source_dict.items():
            if key not in dest_dict:
                self.to_insert.append(row)
        logger.info(f"Найдено {len(self.to_insert)} записей для вставки.")

        # Определяем, что нужно обновить или удалить
        logger.debug("Определение записей для обновления или удаления...")
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
        logger.info(f"Найдено {len(self.to_update)} записей для обновления.")
        logger.info(f"Найдено {len(self.to_delete)} записей для удаления.")
        logger.info("Сравнение данных завершено")

    def get_key(self, row: Dict[str, Any], key_fields: List[str]) -> str:
        # Создаем ключ из указанных полей
        key_parts = []
        for field in key_fields:
            key_parts.append(str(row.get(field, "")))
        key_str = "|".join(key_parts)
        return key_str

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
        logger.info("Начало модификации данных перед выполнением изменений")
        transformation_config = self.config["transformation"]
        logger.debug(f"Конфигурация трансформации для модификации: {transformation_config}")

        # Трансформация данных для вставки
        if transformation_config.get("destination_path"):
            logger.debug(f"Загрузка трансформации для модификации данных из: {transformation_config['destination_path']}")
            transform_func = self.load_transform_function(transformation_config["destination_path"])
            if transform_func:
                logger.debug("Применение трансформации к данным для вставки...")
                self.to_insert = transform_func(self.to_insert)
                logger.info(f"Модификация данных для вставки завершена. Результат: {len(self.to_insert)} записей.")
                # Для обновления нужно трансформировать только "new" часть
                logger.debug("Применение трансформации к новым данным для обновления...")
                for update_item in self.to_update:
                    # Оборачиваем словарь в список, т.к. функция трансформации ожидает список
                    transformed_new_row_list = transform_func([update_item["new"]])
                    if transformed_new_row_list and len(transformed_new_row_list) > 0:
                         update_item["new"] = transformed_new_row_list[0]
                logger.info(f"Модификация новых данных для обновления завершена.")
            else:
                logger.warning(f"Функция трансформации для модификации не найдена в {transformation_config['destination_path']}")
        else:
            logger.debug("Конфигурация трансформации для модификации не указана.")
        logger.info("Модификация данных завершена")

    def execute_changes(self):
        logger.info("Начало выполнения изменений в приемнике")
        dest_config = self.config["destination"]
        destination = self.get_data_source(
            dest_config["type"],
            dest_config["connection_params"]
        )
        try:
            logger.debug("Подключение к приемнику для выполнения изменений...")
            destination.connect()

            # --- Получаем имя таблицы для SQL/MySQL, None для CSV ---
            table_name = dest_config.get("table", None)
            # ------------------------------------------------------

            # Вставляем новые записи
            logger.info(f"Вставка {len(self.to_insert)} новых записей...")
            if self.to_insert:
                 destination.insert_data(self.to_insert, table_name) # Используем новый метод для всех типов
                 logger.info(f"Вставка завершена. Всего вставлено: {len(self.to_insert)}")
            else:
                 logger.info(f"Нет записей для вставки.")

            # Обновляем существующие записи
            logger.info(f"Обновление {len(self.to_update)} существующих записей...")
            if self.to_update:
                destination.update_data(self.to_update, self.config["comparison"]["key_fields"], table_name) # Используем новый метод для всех типов
                logger.info(f"Обновление завершено. Всего обновлено: {len(self.to_update)}")
            else:
                logger.info(f"Нет записей для обновления.")

            # Удаляем записи
            logger.info(f"Удаление {len(self.to_delete)} записей...")
            if self.to_delete:
                destination.delete_data(self.to_delete, self.config["comparison"]["key_fields"], table_name) # Используем новый метод для всех типов
                logger.info(f"Удаление завершено. Всего удалено: {len(self.to_delete)}")
            else:
                logger.info(f"Нет записей для удаления.")

            logger.info("Все изменения успешно применены.")
        except Exception as e:
            logger.error(f"Ошибка при выполнении изменений: {e}")
            # Откат транзакции убран
            raise # Передаем ошибку выше
        finally:
            logger.debug("Отключение от приемника после выполнения изменений...")
            destination.disconnect()

    def run(self):
        logger.info("=== ЗАПУСК ПРОЦЕССА ПЕРЕНОСА ДАННЫХ ===")
        try:
            self.fetch_data()
            self.format_data()
            self.transform_data()
            self.compare_data()
            self.modify_data()
            self.execute_changes()
            logger.info("=== ПРОЦЕСС ПЕРЕНОСА ДАННЫХ УСПЕШНО ЗАВЕРШЕН ===")
        except Exception as e:
            logger.error(f"=== ПРОЦЕСС ПЕРЕНОСА ДАННЫХ ЗАВЕРШЕН С ОШИБКОЙ: {e} ===")
            raise # Передаем ошибку выше, чтобы GUI мог её обработать
