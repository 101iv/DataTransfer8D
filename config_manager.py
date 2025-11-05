import json
from typing import Any, Dict, List, Tuple
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog
import logging

# Настройка логирования для этого модуля
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)  # Создаем логгер для этого файла

# Класс для работы с конфигурацией
class ConfigManager:
    def __init__(self, config_file: str = None):
        self.config_file = config_file
        self.config = {}
        self.new_config = {
            "source": {
                "type": "sql",  # mysql, sql, csv
                "connection_params": {  # параметры подключения к mysql-базе
                    "host": "",
                    "port": 3306,
                    "user": "",
                    "password": "",
                    "database": "",
                    "charset": "utf8mb4"
                }
            },
            "destination": {
                "type": "csv",
                "connection_params": {  # параметры подключения к csv, для SQL lite достаточно указать "path"
                    "path": "test.csv",
                    "delimiter": ","
                }
            },
            "jobs": [  # список заданий, которые программа последовательно выполняет
                {"tables":  # список одинаковых таблиц в источнике и приемнике, программа берет одинаковые поля
                     ["table1", "table2", "..."]  # остальные поля не учитываются
                 },

                # для сложного случая
                {"source": {
                    "query": "",  # sql-запрос для сложной выборки, для csv это путь файла
                    "columns": [],
                    "key_fields": []  # ключевые поля теперь могут быть разные для источника и приемника

                },
                    "destination": {
                        "table": "",  # может быть query для сложной выборки
                        "columns": [],
                        "key_fields": []
                    },
                    "transformation": {
                        "source_path": "",  # путь для скрипта на Python для трансформации после выборки
                        "destination_path": "",  # то же и для приемника, например "jobs/oc15_to_oc3/oc_currency.py"
                        "transform_upd_data_patch": "",  # путь к файлу для обновления данных после сравнения
                        "transform_ins_data_patch": "",  # то же для данных, полученные для вставки в приемник
                        "transform_del_data_patch": "",  # то же для удаления
                    },
                    "comparison": {
                        "key_fields": [] # ключевые поля могут быть одинаковыми
                    }

                },
                {"source": {  # пример job без модификаторов
                    "query": "",
                    },
                    "destination": {
                        "table": "",  # обязательно для приемника, для обновления полученными данными
                        "columns": []
                    },
                    "comparison": {
                        "source_key_fields": [], # такое определение ключей приоритет для программы
                        "destination_key_fields": []
                    }
                }
            ]

        }

    def load_config(self, file_path: str = None):
        logger.debug(f"Попытка загрузки конфигурации из файла: {file_path or self.config_file}")
        path = file_path or self.config_file
        if not path:
            error_msg = "No configuration file specified"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            self.config_file = path
            logger.info(f"Конфигурация успешно загружена из: {path}")
        except FileNotFoundError:
            error_msg = f"Configuration file not found: {path}"
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)
        except json.JSONDecodeError:
            error_msg = f"Invalid JSON in configuration file: {path}"
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)

    def save_config(self, file_path: str = None):
        logger.debug(f"Попытка сохранения конфигурации в файл: {file_path or self.config_file}")
        path = file_path or self.config_file
        if not path:
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if not path:
                logger.info("Операция сохранения отменена пользователем.")
                return

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

        self.config_file = path
        success_msg = f"Configuration saved to: {path}"
        logger.info(success_msg)
        messagebox.showinfo("Success", success_msg)

    def get_config(self) -> Dict[str, Any]:
        logger.debug("Получение текущей конфигурации")
        return self.config

    def set_config(self, new_config: Dict[str, Any]):
        logger.debug("Установка новой конфигурации")
        self.config = new_config

    def _get_similar_fields(self, source_schema: Dict[str, List[Dict[str, Any]]],
                            dest_schema: Dict[str, List[Dict[str, Any]]],
                            source_table: str, dest_table: str) -> List[str]:
        """
        Вспомогательный метод для получения списка одинаковых полей из двух таблиц

        Args:
            source_schema: Словарь схемы источника {table_name: [column_info_dict, ...]}
            dest_schema: Словарь схемы назначения {table_name: [column_info_dict, ...]}
            source_table: Имя таблицы в источнике
            dest_table: Имя таблицы в назначении

        Returns:
            List[str]: Список одинаковых полей (по ключу 'name')
        """
        logger.debug(f"Поиск одинаковых полей для таблиц {source_table} (источник) и {dest_table} (назначение)")
        source_columns = set(col["name"] for col in source_schema.get(source_table, []))
        dest_columns = set(col["name"] for col in dest_schema.get(dest_table, []))
        common_fields = list(source_columns.intersection(dest_columns))
        logger.debug(f"Найдены одинаковые поля: {common_fields}")
        return common_fields

    def _get_primary_key_fields(self, schema: Dict[str, List[Dict[str, Any]]], table_name: str) -> List[str]:
        """
        Вспомогательный метод для получения списка первичных ключей из схемы таблицы

        Args:
            schema: Словарь схемы {table_name: [column_info_dict, ...]}
            table_name: Имя таблицы

        Returns:
            List[str]: Список полей, являющихся первичным ключом (PK)
        """
        logger.debug(f"Поиск первичных ключей для таблицы {table_name}")
        primary_keys = []
        table_schema = schema.get(table_name, [])
        for col_info in table_schema:
            if col_info.get("primary_key", False):  # Предполагаем, что схема уже содержит признак PK
                primary_keys.append(col_info["name"])
        logger.debug(f"Найдены первичные ключи: {primary_keys}")
        return primary_keys

    def _add_jobs_from_tbl_names(self, table_names: List[str], source_schema: Dict[str, List[Dict[str, Any]]],
                                 dest_schema: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Вспомогательный метод для создания новых заданий из списка имен таблиц

        Args:
            table_names: Список имен таблиц
            source_schema: Словарь схемы источника {table_name: [column_info_dict, ...]}
            dest_schema: Словарь схемы назначения {table_name: [column_info_dict, ...]}

        Returns:
            List[Dict]: Список новых заданий
        """
        logger.debug(f"Создание заданий из списка имен таблиц: {table_names}")
        new_jobs = []
        for table_name in table_names:
            logger.debug(f"Обработка таблицы {table_name} для создания задания")
            # Получаем одинаковые поля для таблицы
            similar_fields = self._get_similar_fields(
                source_schema,
                dest_schema,
                table_name,
                table_name
            )

            # Получаем ключевые поля из схем
            source_primary_keys = self._get_primary_key_fields(source_schema, table_name)
            dest_primary_keys = self._get_primary_key_fields(dest_schema, table_name)
            if not source_primary_keys:
                source_primary_keys = dest_primary_keys
            if not dest_primary_keys:
                dest_primary_keys = source_primary_keys

            # Создаем новое задание
            job = {
                "source": {
                    "table": table_name,
                    "columns": similar_fields,
                    "key_fields": source_primary_keys
                },
                "destination": {
                    "table": table_name,
                    "columns": similar_fields,
                    "key_fields": dest_primary_keys
                }
            }
            new_jobs.append(job)
            logger.debug(f"Создано задание для таблицы {table_name}: {job}")

        logger.debug(f"Создано {len(new_jobs)} заданий из имен таблиц.")
        return new_jobs

    def _transform_single_job(self, job: Dict[str, Any], source_schema: Dict[str, List[Dict[str, Any]]],
                              dest_schema: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Обрабатывает один обычный job по правилам:
        - если в source есть ключ table, но нет columns, то получаем колонки из _get_similar_fields для source и destination
        - если в source есть ключ table, но нет key_fields, то получаем ключи из _get_primary_key_fields
        - в destination обязательно должен быть ключ table если нет то ошибка
        - если в destination нет key_fields то получаем ключи из _get_primary_key_fields
        """
        logger.debug(f"Начало трансформации одиночного задания: {job}")
        # Создаем копию job для модификации
        processed_job = job.copy()

        source_info = processed_job.get("source", {})
        dest_info = processed_job.get("destination", {})

        # Проверяем наличие ключа "table" в destination
        if "table" not in dest_info or not dest_info["table"]:
            error_msg = f"Destination 'table' key is required in destination and cannot be empty. destination = {dest_info}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Обработка source
        if "table" in source_info:
            source_table = source_info["table"]
            dest_table = dest_info["table"]
            logger.debug(f"Обработка source таблицы: {source_table}, destination таблицы: {dest_table}")

            # Если columns не указаны, получаем их из _get_similar_fields
            if "columns" not in source_info or source_info["columns"] is None or source_info["columns"] == []:
                logger.debug(f"Колонки для source таблицы {source_table} не указаны, получаем из схемы.")
                similar_cols = self._get_similar_fields(source_schema, dest_schema, source_table, dest_table)
                source_info["columns"] = similar_cols
                dest_info["columns"] = similar_cols
                logger.debug(f"Установлены колонки: {similar_cols}")


            # Если key_fields не указаны, получаем их из _get_primary_key_fields
            if "key_fields" not in source_info or source_info["key_fields"] is None or source_info["key_fields"] == []:
                logger.debug(f"Ключевые поля для source таблицы {source_table} не указаны, получаем из схемы.")
                primary_keys = self._get_primary_key_fields(source_schema, source_table)
                source_info["key_fields"] = primary_keys
                logger.debug(f"Установлены ключевые поля source: {primary_keys}")

            # Обновляем source в processed_job
            processed_job["source"] = source_info

        # Обработка destination
        dest_table = dest_info["table"] # Уже проверено выше
        logger.debug(f"Обработка destination таблицы: {dest_table}")

        # Если key_fields не указаны, получаем их из _get_primary_key_fields
        if "key_fields" not in dest_info or dest_info["key_fields"] is None or dest_info["key_fields"] == []:
            logger.debug(f"Ключевые поля для destination таблицы {dest_table} не указаны, получаем из схемы.")
            primary_keys = self._get_primary_key_fields(dest_schema, dest_table)
            if not primary_keys:
                if "key_fields" not in source_info:
                    logger.error("Не найдены ключевые поля для источника и назначения.")
                else:
                    primary_keys = source_info["key_fields"]
            
            dest_info["key_fields"] = primary_keys
            logger.debug(f"Установлены ключевые поля destination: {primary_keys}")

        # Обновляем destination в processed_job
        processed_job["destination"] = dest_info

        logger.debug(f"Завершена трансформация одиночного задания. Результат: {processed_job}")
        return processed_job


    @classmethod
    def transform_config(cls, user_config: Dict[str, Any], source_schema: Dict[str, List[Dict[str, Any]]],
                         dest_schema: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Метод для преобразования конфига на основе пользовательского конфига и схем баз данных

        Args:
            user_config: Пользовательский конфиг
            source_schema: Словарь схемы источника {table_name: [column_info_dict, ...]}
            dest_schema: Словарь схемы назначения {table_name: [column_info_dict, ...]}

        Returns:
            Dict: Новый преобразованный конфиг
        """
        logger.info("Начало трансформации конфигурации.")
        # Создаем экземпляр ConfigManager для доступа к вспомогательным методам
        config_manager = cls()

        # Создаем копию конфига для модификации
        new_config = user_config.copy()

        # Обрабатываем каждый job в массиве jobs
        transformed_jobs = []
        for i, job in enumerate(user_config.get("jobs", [])):
            logger.debug(f"Обработка задания {i}: {job}")
            # Проверяем наличие ключа tables
            if "tables" in job:
                # Если есть ключ tables, используем add-jobs-from-tbl-names
                table_names = job["tables"]
                logger.info(f"Найден блок 'tables', создаем задания из списка: {table_names}")
                new_jobs = config_manager._add_jobs_from_tbl_names(table_names, source_schema, dest_schema)
                transformed_jobs.extend(new_jobs)
                logger.debug(f"Добавлено {len(new_jobs)} заданий из блока 'tables'.")
            else:
                # Обрабатываем обычный job с помощью нового метода
                logger.debug(f"Обработка одиночного задания {i}.")
                processed_job = config_manager._transform_single_job(job, source_schema, dest_schema)
                transformed_jobs.append(processed_job)
                logger.debug(f"Задание {i} обработано и добавлено.")

        # Заменяем jobs в новом конфиге
        new_config["jobs"] = transformed_jobs
        logger.info(f"Трансформация завершена. Обработано {len(transformed_jobs)} заданий.")
        return new_config
