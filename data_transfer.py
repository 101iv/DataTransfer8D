# data_transfer.py
import importlib.util
import logging  # Добавляем импорт модуля logging
import os  # Добавлено для проверки существования файла в load_transform_function
from typing import Any, Dict, List, Tuple
from data_sources import DataSource, SQLDataSource, CSVDataSource, MySqlDataSource


# Настройка логирования для этого модуля
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)  # Создаем логгер для этого файла


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
        # Инициализируем атрибуты для хранения экземпляров DataSource
        self.source = None
        self.destination = None

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

    def _process_data(self, type: str) -> None:
        """
        Унифицированный метод для загрузки, форматирования и трансформации данных из одного источника (источник или приемник).

        :param type: Имя атрибута для хранения экземпляра DataSource ('source' или 'destination').
        """
        source_type = self.config[type]["type"]
        connection_params = self.config[type]["connection_params"]
        query = self.config[type]["query"]
        filters = self.config[type].get("filters", {})

        # Создаём экземпляр DataSource
        logger.debug(f"Создание экземпляра DataSource для {type}...")
        data_source_instance = self.get_data_source(source_type, connection_params)
        # Сохраняем экземпляр в атрибуте класса
        setattr(self, type, data_source_instance)

        # Подключаемся к источнику данных
        logger.debug(f"Подключение к {type}...")
        data_source_instance.connect()

        # Загрузка данных
        logger.debug(f"Загрузка данных из {type}...")
        raw_data = data_source_instance.fetch_data(query, filters)
        logger.info(f"Загружено {len(raw_data)} записей из {type}.")
        setattr(self, type + "_data", raw_data)

        # Форматирование данных
        logger.debug(f"Форматирование {type} (type: {source_type})...")
        if source_type:
            formatted_data = data_source_instance.standard_formatting(raw_data)

        else:
            # Если форматирование не определено, просто копируем
            formatted_data = [dict(row) for row in raw_data]
        logger.info(
            f"Форматирование {type} завершено. Обработано {len(formatted_data)} записей.")
        setattr(self, "formatted_" + type, formatted_data)

    def fetch_data(self):
        logger.info("Создаём и подключаем источники данных")
        # Загружаем и форматируем данные из источника
        self._process_data("source")
        # Загружаем и форматируем данные из приемника
        self._process_data("destination")
        logger.info("Завершена загрузка данных")

    def _apply_transform(self, type):
        """
        Вспомогательный метод для применения трансформации к данным, если путь к файлу указан в конфигурации.
        """
        transformation_config = self.config["transformation"]
        path = transformation_config.get(type + '_path')
        if path:
            logger.debug(f"Загрузка трансформации для {type} из: {path}")
            transform_func = self.load_transform_function(path)
            if transform_func:
                logger.debug(
                    f"Функция трансформации для {type} загружена, применяем...")
                current_data = getattr(self, 'formatted_' + type)
                transformed_data = transform_func(current_data)
                setattr(self, 'formatted_' + type, transformed_data)
                logger.info(
                    f"Трансформация {type} применена. Результат: {len(transformed_data)} записей.")
            else:
                logger.warning(
                    f"Функция трансформации для {type} не найдена в {path}")

    def modify_data_after_fetch(self):
        logger.info("Начало модификации данных после выборки")
        logger.debug(f"Конфигурация трансформации: {self.config['transformation']}")

        # Трансформация исходных данных
        self._apply_transform('source_path', 'formatted_source', 'transform_source')

        # Трансформация данных приемника
        self._apply_transform('destination_path', 'formatted_destination', 'transform_destination')

        logger.info("Модификация данных после выборки завершена")

    def load_transform_function(self, file_path: str, transform_func_name):
        # Загружаем функцию трансформации из файла
        logger.debug(f"Попытка загрузки функции трансформации из {file_path}")
        if not os.path.exists(file_path):
            logger.error(f"Файл трансформации не найден: {file_path}")
            return None
        try:
            spec = importlib.util.spec_from_file_location(transform_func_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Предполагаем, что в файле есть функция transform
            if hasattr(module, transform_func_name):
                func = getattr(module, transform_func_name)
                logger.debug(f"Функция {transform_func_name} найдена в {file_path}")
                return func
            else:
                logger.warning(f"Функция {transform_func_name} не найдена в {file_path}")
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

    def _apply_transform(self, path_key: str, data_attr_name: str, transform_func_name: str, additional_args=None):
        """
        Универсальный метод для применения трансформации к данным.

        :param path_key: Ключ в конфигурации для получения пути к файлу с функцией
        :param transform_func_name: Имя функции трансформации в файле
        :param additional_args: Дополнительные аргументы, передаваемые в функцию (опционально)
        """
        transformation_config = self.config["transformation"]
        path = transformation_config.get(path_key)
        if path:
            logger.debug(f"Загрузка трансформации: функция {transform_func_name} для {data_attr_name} из: {path}")
            transform_func = self.load_transform_function(path, transform_func_name)
            if transform_func:
                logger.debug(f"Функция {transform_func_name} для {data_attr_name} загружена, применяем...")
                current_data = getattr(self, data_attr_name)
                # Подготовка аргументов для вызова функции
                args = [current_data]
                if additional_args:
                    args.extend(additional_args)
                transformed_data = transform_func(*args)
                setattr(self, data_attr_name, transformed_data)
                logger.info(
                    f"Трансформация {transform_func_name} для {data_attr_name} применена. Результат: {len(transformed_data)} записей.")
            else:
                logger.warning(f"Функция {transform_func_name} для {data_attr_name} не найдена в {path}")

    def modify_data_after_compare(self):
        logger.info("Начало модификации данных после сравнения")
        logger.debug(f"Конфигурация трансформации : {self.config['transformation']}")

        # Трансформация данных для обновления
        if self.to_update:
            self._apply_transform('transform_upd_data_patch', 'to_update', 'transform_ins_data',
                                  additional_args=[self.formatted_source, self.formatted_destination])

        # Трансформация данных для вставки
        if self.to_insert:
            self._apply_transform('transform_ins_data_patch', 'to_insert', 'transform_upd_data',
                              additional_args=[self.formatted_source, self.formatted_destination])

        # Трансформация данных для удаления
        if self.to_delete:
            self._apply_transform('transform_del_data_patch', 'to_delete', 'transform_del_data',
                              additional_args=[self.formatted_source, self.formatted_destination])

        logger.info("Модификация данных после сравнения завершена")

    def execute_changes(self):
        logger.info("Начало выполнения изменений в приемнике")
        dest_config = self.config["destination"]

        # Используем уже созданный и подключенный экземпляр destination
        destination_instance = self.destination  # Предполагается, что destination уже создан и подключен в fetch_data
        # Подключаться не нужно, так как уже подключены

        try:
            # --- Получаем имя таблицы для SQL/MySQL, None для CSV ---
            table_name = dest_config.get("table", None)
            # ------------------------------------------------------

            # Вставляем новые записи
            logger.info(f"Вставка {len(self.to_insert)} новых записей...")
            if self.to_insert:
                destination_instance.insert_data(self.to_insert, table_name)  # Используем новый метод для всех типов
                logger.info(f"Вставка завершена. Всего вставлено: {len(self.to_insert)}")
            else:
                logger.info(f"Нет записей для вставки.")

            # Обновляем существующие записи
            logger.info(f"Обновление {len(self.to_update)} существующих записей...")
            if self.to_update:
                destination_instance.update_data(self.to_update, self.config["comparison"]["key_fields"],
                                                 table_name)  # Используем новый метод для всех типов
                logger.info(f"Обновление завершено. Всего обновлено: {len(self.to_update)}")
            else:
                logger.info(f"Нет записей для обновления.")

            # Удаляем записи
            logger.info(f"Удаление {len(self.to_delete)} записей...")
            if self.to_delete:
                destination_instance.delete_data(self.to_delete, self.config["comparison"]["key_fields"],
                                                 table_name)  # Используем новый метод для всех типов
                logger.info(f"Удаление завершено. Всего удалено: {len(self.to_delete)}")
            else:
                logger.info(f"Нет записей для удаления.")

            logger.info("Все изменения успешно применены.")
        except Exception as e:
            logger.error(f"Ошибка при выполнении изменений: {e}")
            # Откат транзакции убран
            raise  # Передаем ошибу выше
        finally:
            # Отключаемся от приемника и источника только после выполнения всех изменений
            logger.debug("Отключение от источника и приемника после выполнения изменений...")
            if self.destination and hasattr(self.destination, 'disconnect'):
                self.destination.disconnect()
            if self.source and hasattr(self.source, 'disconnect'):
                self.source.disconnect()

    def run(self):
        logger.info("=== ЗАПУСК ПРОЦЕССА ПЕРЕНОСА ДАННЫХ ===")
        try:
            self.fetch_data()
            self.modify_data_after_fetch()
            self.compare_data()
            self.modify_data_after_compare()
            self.execute_changes()
            logger.info("=== ПРОЦЕСС ПЕРЕНОСА ДАННЫХ УСПЕШНО ЗАВЕРШЕН ===")
        except Exception as e:
            logger.error(f"=== ПРОЦЕСС ПЕРЕНОСА ДАННЫХ ЗАВЕРШЕН С ОШИБКОЙ: {e} ===")
            raise  # Передаем ошибку выше, чтобы GUI мог её обработать
