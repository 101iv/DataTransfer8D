# job_manager.py
import logging
from typing import Any, Dict, List
from data_transfer import DataTransfer  # Импортируем оригинальный DataTransfer
from data_sources import DataSource, SQLDataSource, CSVDataSource, MySqlDataSource

logger = logging.getLogger(__name__)  # Создаем логгер для этого файла


class JobManager:
    """
    Класс для выполнения нескольких задач переноса данных (jobs) на основе одного конфига.
    """

    def __init__(self, config: Dict[str, Any]):
        logger.info("Инициализация JobManager")
        self.config = config
        # Извлекаем список задач (jobs) из конфига
        self.jobs = config.get("jobs", [])
        self.source_instance = None
        self.destination_instance = None
        # --- НОВОЕ: Инициализируем атрибуты для хранения итоговых результатов ---
        self.to_insert: List[Any] = []
        self.to_update: List[Any] = []
        self.to_delete: List[Any] = []
        # ------------------------------------------------------------

    def run(self):
        """
        Выполняет все задачи переноса данных из конфига.
        """
        logger.info("=== ЗАПУСК ПРОЦЕССА МНОЖЕСТВЕННОГО ПЕРЕНОСА ДАННЫХ ===")
        try:
            self._connect_sources()
            # --- НОВОЕ: Обнуляем списки перед началом, если это может быть повторный запуск ---
            self.to_insert = []
            self.to_update = []
            self.to_delete = []
            # ------------------------------------------------------------

            for i, job_config in enumerate(self.jobs):
                logger.info(f"--- НАЧАЛО ВЫПОЛНЕНИЯ JOB {i + 1}/{len(self.jobs)} ---")
                logger.debug(f"Конфигурация job {i + 1}: {job_config}")

                # Создаем экземпляр оригинального DataTransfer для каждой задачи
                transfer = DataTransfer(job_config, self.source_instance, self.destination_instance)

                # Запускаем выполнение задачи
                transfer.run() # transfer.run() внутри себя вызывает fetch, compare и т.д., заполняя transfer.to_insert и т.д.

                # --- НОВОЕ: Суммируем результаты текущей задачи к итоговым ---
                self.to_insert.extend(transfer.to_insert)
                self.to_update.extend(transfer.to_update)
                self.to_delete.extend(transfer.to_delete)
                # ------------------------------------------------------------

                logger.info(f"--- КОНЕЦ ВЫПОЛНЕНИЯ JOB {i + 1}/{len(self.jobs)} ---")
                logger.info(f"Статистика для JOB {i + 1}: Вставка={len(transfer.to_insert)}, Обновление={len(transfer.to_update)}, Удаление={len(transfer.to_delete)}")

            self._disconnect_sources()

            # Логируем итоговую статистику
            total_inserted = len(self.to_insert)
            total_updated = len(self.to_update)
            total_deleted = len(self.to_delete)
            logger.info(f"=== ИТОГОВАЯ СТАТИСТИКА ПО ВСЕМ JOBS: Вставка={total_inserted}, Обновление={total_updated}, Удаление={total_deleted} ===")

            logger.info("=== ПРОЦЕСС МНОЖЕСТВЕННОГО ПЕРЕНОСА ДАННЫХ УСПЕШНО ЗАВЕРШЕН ===")
        except Exception as e:
            logger.error(f"=== ПРОЦЕСС МНОЖЕСТВЕННОГО ПЕРЕНОСА ДАННЫХ ЗАВЕРШЕН С ОШИБКОЙ: {e} ===")
            # Важно: даже при ошибке списки могут быть частично заполнены, если ошибка произошла не сразу
            # или после выполнения части задач. GUI может использовать эти частичные данные.
            # Если вы хотите, чтобы при ошибке списки были пустыми, раскомментируйте следующие строки:
            # self.to_insert = []
            # self.to_update = []
            # self.to_delete = []
            raise  # Передаем ошибку выше, чтобы GUI мог её обработать


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

    def _connect_sources(self):
        """
        Подключается к источникам данных (источник и приемник).
        """
        logger.debug("Подключение к источникам данных...")

        source_config = self.config.get("source", {})
        dest_config = self.config.get("destination", {})

        source_type = source_config.get("type", "")
        dest_type = dest_config.get("type", "")
        source_connection_params = source_config.get("connection_params", {})
        dest_connection_params = dest_config.get("connection_params", {})

        if not source_type or not dest_type:
            raise ValueError("Тип источника и приемника должны быть указаны в конфигурации.")

        # Подключение к источнику
        logger.debug(f"Подключение к источнику ({source_type})...")
        self.source_instance = self.get_data_source(source_type, source_connection_params)
        self.source_instance.connect()

        # Подключение к приемнику
        logger.debug(f"Подключение к приемнику ({dest_type})...")
        self.destination_instance = self.get_data_source(dest_type, dest_connection_params)
        self.destination_instance.connect()

    def _disconnect_sources(self):
        """
        Отключается от источников данных (источник и приемник).
        """
        logger.debug("Отключение от источников данных...")
        if self.source_instance and hasattr(self.source_instance, 'disconnect'):
            self.source_instance.disconnect()
        if self.destination_instance and hasattr(self.destination_instance, 'disconnect'):
            self.destination_instance.disconnect()
