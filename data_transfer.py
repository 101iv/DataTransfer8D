# data_transfer.py
import importlib.util
import logging  # Добавляем импорт модуля logging
import os  # Добавлено для проверки существования файла в load_transform_function
from typing import Any, Dict, List, Tuple
from data_sources import DataSource, SQLDataSource, CSVDataSource, MySqlDataSource

# Импортируем функции форматирования
from data_sources.sql_source import standard_formatting as sql_formatting
from data_sources.mysql_source import standard_formatting as mysql_formatting
from data_sources.csv_source import standard_formatting as csv_formatting

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

    def _process_data_source(self, config_part: Dict[str, Any], data_attr_name: str, formatted_attr_name: str) -> None:
        """
        Унифицированный метод для загрузки, форматирования и трансформации данных из одного источника (источник или приемник).

        :param config_part: Конфигурационная секция ('source' или 'destination').
        :param data_attr_name: Имя атрибута для хранения необработанных данных ('source_data' или 'destination_data').
        :param formatted_attr_name: Имя атрибута для хранения отформатированных данных ('formatted_source' или 'formatted_destination').
        """
        source_type = config_part["type"]
        connection_params = config_part["connection_params"]
        query = config_part["query"]
        filters = config_part.get("filters", {})

        # Загрузка данных
        logger.debug(f"Подключение к {data_attr_name.replace('_data', '')}...")
        data_source = self.get_data_source(source_type, connection_params)
        try:
            data_source.connect()
            logger.debug(f"Загрузка данных из {data_attr_name.replace('_data', '')}...")
            raw_data = data_source.fetch_data(query, filters)
            logger.info(f"Загружено {len(raw_data)} записей из {data_attr_name.replace('_data', '')}.")
            setattr(self, data_attr_name, raw_data)
        finally:
            logger.debug(f"Отключение от {data_attr_name.replace('_data', '')}...")
            data_source.disconnect()

        # Форматирование данных
        logger.debug(f"Форматирование {data_attr_name.replace('_data', '')} (type: {source_type})...")
        if source_type == "sql":
            formatted_data = sql_formatting(getattr(self, data_attr_name))
        elif source_type == "mysql":
            formatted_data = mysql_formatting(getattr(self, data_attr_name))
        elif source_type == "csv":
            formatted_data = csv_formatting(getattr(self, data_attr_name))
        else:
            # Если форматирование не определено, просто копируем
            formatted_data = [dict(row) for row in getattr(self, data_attr_name)]
        logger.info(
            f"Форматирование {data_attr_name.replace('_data', '')} завершено. Обработано {len(formatted_data)} записей.")
        setattr(self, formatted_attr_name, formatted_data)

    def fetch_data(self):
        logger.info("Начало загрузки данных")
        # Загружаем и форматируем данные из источника
        self._process_data_source(self.config["source"], "source_data", "formatted_source")

        # Загружаем и форматируем данные из приемника
        self._process_data_source(self.config["destination"], "destination_data", "formatted_destination")
        logger.info("Завершена загрузка данных")

    def _apply_transform_if_configured(self, path_key: str, data_attr_name: str):
        """
        Вспомогательный метод для применения трансформации к данным, если путь к файлу указан в конфигурации.

        :param path_key: Ключ в конфигурации transformation ('source_path' или 'destination_path').
        :param data_attr_name: Имя атрибута, содержащего данные для трансформации ('formatted_source' или 'formatted_destination').
        """
        transformation_config = self.config["transformation"]
        path = transformation_config.get(path_key)
        if path:
            logger.debug(f"Загрузка трансформации для {data_attr_name.replace('formatted_', '')} из: {path}")
            transform_func = self.load_transform_function(path)
            if transform_func:
                logger.debug(
                    f"Функция трансформации для {data_attr_name.replace('formatted_', '')} загружена, применяем...")
                current_data = getattr(self, data_attr_name)
                transformed_data = transform_func(current_data)
                setattr(self, data_attr_name, transformed_data)
                logger.info(
                    f"Трансформация {data_attr_name.replace('formatted_', '')} применена. Результат: {len(transformed_data)} записей.")
            else:
                logger.warning(
                    f"Функция трансформации для {data_attr_name.replace('formatted_', '')} не найдена в {path}")

    def transform_data(self):
        logger.info("Начало трансформации данных")
        logger.debug(f"Конфигурация трансформации: {self.config['transformation']}")

        # Трансформация исходных данных
        self._apply_transform_if_configured('source_path', 'formatted_source')

        # Трансформация данных приемника
        self._apply_transform_if_configured('destination_path', 'formatted_destination')

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

    def _apply_transform_to_operation_data(self, path_key: str, data_attr_name: str, transform_func_name: str):
        """
        Вспомогательный метод для применения трансформации к спискам операций (to_insert, to_update, to_delete),
        передавая им также formatted_source и formatted_destination.

        :param path_key: Ключ в конфигурации transformation ('transform_ins_data', 'transform_upd_data', 'transform_del_data').
        :param data_attr_name: Имя атрибута, содержащего данные для трансформации ('to_insert', 'to_update', 'to_delete').
        :param transform_func_name: Имя функции трансформации в файле (предполагается 'transform').
        """
        transformation_config = self.config["transformation"]
        path = transformation_config.get(path_key)
        if path:
            logger.debug(f"Загрузка трансформации {transform_func_name} для {data_attr_name} из: {path}")
            transform_func = self.load_transform_function(path)
            if transform_func:
                logger.debug(f"Функция {transform_func_name} для {data_attr_name} загружена, применяем...")
                current_data = getattr(self, data_attr_name)
                # Передаём текущие данные и дополнительные источники
                transformed_data = transform_func(current_data, self.formatted_source, self.formatted_destination)
                setattr(self, data_attr_name, transformed_data)
                logger.info(
                    f"Трансформация {transform_func_name} для {data_attr_name} применена. Результат: {len(transformed_data)} записей.")
            else:
                logger.warning(f"Функция {transform_func_name} для {data_attr_name} не найдена в {path}")

    def modify_data(self):
        logger.info("Начало модификации данных перед выполнением изменений")
        logger.debug(f"Конфигурация трансформации для модификации операций: {self.config['transformation']}")

        # Трансформация данных для вставки
        self._apply_transform_to_operation_data('transform_ins_data', 'to_insert', 'transform_ins_data')

        # Трансформация данных для обновления
        self._apply_transform_to_operation_data('transform_upd_data', 'to_update', 'transform_upd_data')

        # Трансформация данных для удаления
        self._apply_transform_to_operation_data('transform_del_data', 'to_delete', 'transform_del_data')

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
                destination.insert_data(self.to_insert, table_name)  # Используем новый метод для всех типов
                logger.info(f"Вставка завершена. Всего вставлено: {len(self.to_insert)}")
            else:
                logger.info(f"Нет записей для вставки.")

            # Обновляем существующие записи
            logger.info(f"Обновление {len(self.to_update)} существующих записей...")
            if self.to_update:
                destination.update_data(self.to_update, self.config["comparison"]["key_fields"],
                                        table_name)  # Используем новый метод для всех типов
                logger.info(f"Обновление завершено. Всего обновлено: {len(self.to_update)}")
            else:
                logger.info(f"Нет записей для обновления.")

            # Удаляем записи
            logger.info(f"Удаление {len(self.to_delete)} записей...")
            if self.to_delete:
                destination.delete_data(self.to_delete, self.config["comparison"]["key_fields"],
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
            logger.debug("Отключение от приемника после выполнения изменений...")
            destination.disconnect()

    def run(self):
        logger.info("=== ЗАПУСК ПРОЦЕССА ПЕРЕНОСА ДАННЫХ ===")
        try:
            self.fetch_data()
            self.transform_data()
            self.compare_data()
            self.modify_data()
            self.execute_changes()
            logger.info("=== ПРОЦЕСС ПЕРЕНОСА ДАННЫХ УСПЕШНО ЗАВЕРШЕН ===")
        except Exception as e:
            logger.error(f"=== ПРОЦЕСС ПЕРЕНОСА ДАННЫХ ЗАВЕРШЕН С ОШИБКОЙ: {e} ===")
            raise  # Передаем ошибку выше, чтобы GUI мог её обработать