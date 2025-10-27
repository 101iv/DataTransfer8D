# logic.py
import json, sys
import logging
from PyQt5.QtCore import QObject, pyqtSignal
from job_manager import JobManager
from config_manager import ConfigManager
from connectors import SQLDataSource, MySqlDataSource, CSVDataSource


class DataTransferLogic(QObject):
    """
    Класс, содержащий всю бизнес-логику приложения.
    """
    # Сигналы для обновления GUI
    log_message_signal = pyqtSignal(str)
    schema_loaded_signal = pyqtSignal(dict, str)  # (schema_dict, schema_type)
    data_loaded_signal = pyqtSignal(list, list)  # (rows, columns)
    transfer_finished_signal = pyqtSignal(int, int, int, str)  # (inserted, updated, deleted, status)
    progress_update_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.config_manager = ConfigManager()
        self.current_config = {}
        # атрибуты для хранения исходных схем
        self.source_schema = {}
        self.dest_schema = {}

    def set_config(self, config):
        """Устанавливает текущую конфигурацию."""
        self.current_config = config
        self.config_manager.set_config(config)

    def get_config(self):
        """Возвращает текущую конфигурацию."""
        return self.current_config

    def load_config_from_file(self, file_path):
        """Загружает конфигурацию из файла."""
        try:
            self.config_manager.load_config(file_path)
            self.current_config = self.config_manager.get_config()
            self.log_message_signal.emit(f"Configuration loaded from: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            self.log_message_signal.emit(f"Error loading configuration: {e}")
            return False

    def save_config_to_file(self, file_path):
        """Сохраняет текущую конфигурацию в файл."""
        try:
            config_to_save = self.get_config()
            self.config_manager.set_config(config_to_save)
            self.config_manager.config_file = file_path  # Обновляем путь
            self.config_manager.save_config()
            self.log_message_signal.emit(f"Configuration saved to: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            self.log_message_signal.emit(f"Error saving configuration: {e}")
            return False

    def create_default_config(self):
        """Создает и устанавливает конфигурацию по умолчанию."""
        default_config = self.config_manager.new_config
        self.set_config(default_config)
        self.log_message_signal.emit("Default configuration created.")
        return default_config

    def load_schema(self, schema_type):
        """
        Загружает схему из источника или приемника.
        """
        try:
            config = self.get_config()
            config_key = schema_type
            db_config = config.get(config_key, {})
            db_type = db_config.get("type", "")
            connection_params = db_config.get("connection_params", {})

            source = self._get_data_source(db_type, connection_params)
            source.connect()
            schema = source.get_schema()
            source.disconnect()

            # Сохраняем загруженную схему в соответствующий атрибут
            if schema_type == "source":
                self.source_schema = schema
            elif schema_type == "destination":
                self.dest_schema = schema

            self.schema_loaded_signal.emit(schema, schema_type)
            self.log_message_signal.emit(f"{schema_type.capitalize()} schema loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load {schema_type} schema: {e}")
            self.log_message_signal.emit(f"Failed to load {schema_type} schema: {e}")

    def load_data(self, table_name, schema_type):
        """
        Загружает данные из таблицы.
        """
        try:
            config = self.get_config()
            config_key = schema_type
            db_config = config.get(config_key, {})
            db_type = db_config.get("type", "")
            connection_params = db_config.get("connection_params", {})

            source = self._get_data_source(db_type, connection_params)
            source.connect()
            query = f"SELECT * FROM {table_name} LIMIT 10"
            rows = source.fetch_data(query)
            source.disconnect()

            if rows:
                columns = list(rows[0].keys())
            else:
                columns = []
                rows = []

            self.data_loaded_signal.emit(rows, columns)
            self.log_message_signal.emit(f"Data loaded from table '{table_name}' in {schema_type} schema.")
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            self.log_message_signal.emit(f"Failed to load  {e}")

    def transform_config(self):
        """
        Трансформирует конфигурацию на основе схем.
        """
        try:
            config = self.get_config()
            source_schema = self._load_schema_from_config("source")
            dest_schema = self._load_schema_from_config("destination")
            transformed_config = self.config_manager.transform_config(config, source_schema, dest_schema)
            self.log_message_signal.emit("Configuration transformed successfully")
            return transformed_config
        except Exception as e:
            self.logger.error(f"Failed to transform configuration: {e}")
            self.log_message_signal.emit(f"Failed to transform configuration: {e}")
            return None

    def run_transfer(self):
        """Запускает процесс переноса данных."""
        self.logger.info("--- ЗАПУСК ПЕРЕНОСА ИЗ LOGIC ---")
        self.progress_update_signal.emit(0)
        try:
            config = self.get_config()
            # Этот метод будет вызываться в отдельном потоке через TransferWorker
            # Поэтому возвращаем config, который передаст TransferWorker
            return config
        except Exception as e:
            self.logger.error(f"--- ОШИБКА подготовки переноса ИЗ LOGIC: {e} ---")
            self.progress_update_signal.emit(0)
            self.transfer_finished_signal.emit(0, 0, 0, f"preparation failed: {e}")
            return None

    def save_schema_to_json(self, schema_type, file_path):
        """Сохраняет ранее загруженную схему в JSON файл."""
        try:
            # Выбираем схему из атрибута
            schema_to_save = self.source_schema if schema_type == "source" else self.dest_schema
            if not schema_to_save:
                 self.logger.warning(f"No {schema_type} schema loaded to save.")
                 self.log_message_signal.emit(f"No {schema_type} schema loaded to save.")
                 return False

            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(schema_to_save, f, indent=2, ensure_ascii=False)
                self.log_message_signal.emit(f"Schema saved to: {file_path}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to save {schema_type} schema: {e}")
            self.log_message_signal.emit(f"Error saving {schema_type} schema: {e}")
            return False

    def load_schema_from_json(self, file_path):
        """Загружает схему из JSON файла."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
            self.log_message_signal.emit(f"Schema loaded from: {file_path}")
            return schema
        except Exception as e:
            self.logger.error(f"Failed to load schema from {file_path}: {e}")
            self.log_message_signal.emit(f"Error loading schema: {e}")
            return None

    def save_data_to_json(self, rows, columns, file_path):
        """Сохраняет данные таблицы в JSON файл."""
        try:
            # Преобразуем список словарей в список списков значений, если нужно
            # Или оставим как список словарей
            # rows - это уже список словарей, где ключи - это колонки
            # Создадим структуру: {"columns": [...], "data": [...]}
            data_to_save = {"columns": columns, "data": rows}
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            self.log_message_signal.emit(f"Table data saved to: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to save table data to {file_path}: {e}")
            self.log_message_signal.emit(f"Error saving table data: {e}")

    def load_data_from_json(self, file_path):
        """Загружает данные таблицы из JSON файла."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data_loaded = json.load(f)
            rows = data_loaded.get("data", [])
            columns = data_loaded.get("columns", [])
            self.log_message_signal.emit(f"Table data loaded from: {file_path}")
            return rows, columns
        except Exception as e:
            self.logger.error(f"Failed to load table data from {file_path}: {e}")
            self.log_message_signal.emit(f"Error loading table data: {e}")
            return [], []

    def _get_data_source(self, db_type, connection_params):
        """Вспомогательный метод для создания экземпляра источника данных."""
        if db_type == "mysql":
            return MySqlDataSource(connection_params)
        elif db_type == "sql":
            return SQLDataSource(connection_params)
        elif db_type == "csv":
            return CSVDataSource(connection_params)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

    def _load_schema_from_config(self, schema_type):
        """Вспомогательный метод для загрузки схемы из конфига."""
        config = self.get_config()
        config_key = schema_type
        db_config = config.get(config_key, {})
        db_type = db_config.get("type", "")
        connection_params = db_config.get("connection_params", {})
        source = self._get_data_source(db_type, connection_params)
        source.connect()
        schema = source.get_schema()
        source.disconnect()
        return schema


def run_cli_transfer(config_path):
    """Функция для запуска переноса в CLI режиме."""
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    absolute_config_path = os.path.abspath(config_path)

    try:
        config_manager = ConfigManager(config_file=absolute_config_path)
        config_manager.load_config(absolute_config_path)
        config = config_manager.get_config()
        print(f"Configuration loaded from: {absolute_config_path}")
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1 # Ошибка

    try:
        print("Starting data transfer job...")
        transfer = JobManager(config)
        transfer.run()
        print("Transfer completed successfully.")
        print(f"- {len(transfer.to_insert)} records inserted")
        print(f"- {len(transfer.to_update)} records updated")
        print(f"- {len(transfer.to_delete)} records deleted")
        return 0 # Успех
    except Exception as e:
        print(f"Transfer failed: {e}", file=sys.stderr)
        return 1 # Ошибка