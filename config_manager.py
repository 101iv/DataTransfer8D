# config_manager.py
import json
from typing import Any, Dict, List, Tuple
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog


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
        path = file_path or self.config_file
        if not path:
            raise ValueError("No configuration file specified")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            self.config_file = path
        except FileNotFoundError:
            messagebox.showerror("Error", f"Configuration file not found: {path}")
        except json.JSONDecodeError:
            messagebox.showerror("Error", f"Invalid JSON in configuration file: {path}")

    def save_config(self, file_path: str = None):
        path = file_path or self.config_file
        if not path:
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if not path:
                return

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

        self.config_file = path
        messagebox.showinfo("Success", f"Configuration saved to: {path}")

    def get_config(self) -> Dict[str, Any]:
        return self.config

    def set_config(self, new_config: Dict[str, Any]):
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
        source_columns = set(col["name"] for col in source_schema.get(source_table, []))
        dest_columns = set(col["name"] for col in dest_schema.get(dest_table, []))
        return list(source_columns.intersection(dest_columns))

    def _get_primary_key_fields(self, schema: Dict[str, List[Dict[str, Any]]], table_name: str) -> List[str]:
        """
        Вспомогательный метод для получения списка первичных ключей из схемы таблицы

        Args:
            schema: Словарь схемы {table_name: [column_info_dict, ...]}
            table_name: Имя таблицы

        Returns:
            List[str]: Список полей, являющихся первичным ключом (PK)
        """
        primary_keys = []
        table_schema = schema.get(table_name, [])
        for col_info in table_schema:
            if col_info.get("primary_key", False):  # Предполагаем, что схема уже содержит признак PK
                primary_keys.append(col_info["name"])
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
        new_jobs = []
        for table_name in table_names:
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

        return new_jobs

    def _transform_single_job(self, job: Dict[str, Any], source_schema: Dict[str, List[Dict[str, Any]]],
                              dest_schema: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Обрабатывает один обычный job по правилам:
        - если в source есть ключ table но нет columns то получаем колонки из _get_similar_fields
        - если в source есть ключ table но нет key_fields то получаем ключи из _get_primary_key_fields
        - в destination обязательно должен быть  ключ table если нет то ошибка
        - если в destination нет columns то получаем колонки из _get_similar_fields
        - если в destination нет key_fields то получаем ключи из _get_primary_key_fields

        Args:
            job: Словарь job'а для обработки
            source_schema: Словарь схемы источника
            dest_schema: Словарь схемы назначения

        Returns:
            Dict: Обновленный job
        """
        # Работаем с оригинальным job, но будем аккуратно обновлять вложенные структуры
        # Не создаем копию job сразу, а будем копировать только изменяемые вложенные словари

        source_info = job.get("source", {})
        dest_info = job.get("destination", {})

        # --- Проверка destination на наличие table ---
        dest_table = dest_info.get("table")
        if dest_table is None:
            raise ValueError("Destination table is required but not found in job.")

        # --- Обработка source ---
        source_table = source_info.get("table")  # Может быть None, если нет 'table'

        # Если в source есть 'table' и нет 'columns'
        if source_table is not None and ("columns" not in source_info or not source_info["columns"]):
            # Проверим, есть ли таблица в source_schema
            if source_schema and source_table in source_schema:
                # Проверим, есть ли таблица в dest_schema
                if dest_schema and dest_table in dest_schema:
                    # Получаем схожие поля
                    similar_fields = self._get_similar_fields(
                        source_schema, dest_schema, source_table, dest_table
                    )
                    # Создаем копию source_info, чтобы не изменять оригинальный
                    updated_source_info = source_info.copy()
                    updated_source_info["columns"] = similar_fields
                    # Обновляем копию job, в которую вставляем обновленный source_info
                    updated_job = job.copy()
                    updated_job["source"] = updated_source_info
                    print(
                        f"DEBUG: Set source columns for job with table '{source_table}' -> '{dest_table}': {similar_fields}")
                    # Присваиваем job для дальнейших изменений
                    job = updated_job
                    source_info = updated_source_info  # Обновляем переменную для последующего использования
                else:
                    print(
                        f"DEBUG: Destination table '{dest_table}' not found in dest_schema. Cannot infer source columns.")
            else:
                print(f"DEBUG: Source table '{source_table}' not found in source_schema. Cannot infer source columns.")

        # Если в source есть 'table' и нет 'key_fields'
        if source_table is not None and ("key_fields" not in source_info or not source_info["key_fields"]):
            if source_schema and source_table in source_schema:
                primary_keys = self._get_primary_key_fields(source_schema, source_table)
                # Обновляем source_info
                updated_source_info = source_info.copy()
                updated_source_info["key_fields"] = primary_keys
                # Обновляем копию job, в которую вставляем обновленный source_info
                updated_job = job.copy()
                updated_job["source"] = updated_source_info
                print(f"DEBUG: Set source key_fields for table '{source_table}': {primary_keys}")
                job = updated_job
                source_info = updated_source_info  # Обновляем переменную для последующего использования
            else:
                print(
                    f"DEBUG: Source table '{source_table}' not found in source_schema. Cannot infer source key_fields.")

        # --- Обработка destination ---
        # dest_table уже проверен выше

        # Обновляем dest_info, если job был скопирован ранее
        dest_info = job.get("destination", {})

        # Если в destination нет 'columns'
        if "columns" not in dest_info or not dest_info["columns"]:
            # Нужно получить source_table, если он был определен ранее в этом же job
            current_source_info = job.get("source", {})  # Берем обновленный source, если он был изменен
            current_source_table = current_source_info.get("table",
                                                           source_table)  # Используем обновленный, если есть, иначе исходный
            if current_source_table is not None:  # Убедимся, что source_table определена
                if dest_schema and dest_table in dest_schema:
                    # Проверим, есть ли таблица в source_schema (используем исходный source_table, т.к. он мог быть в обновленном, но если нет, то из оригинального job)
                    if source_schema and current_source_table in source_schema:
                        similar_fields = self._get_similar_fields(
                            source_schema, dest_schema, current_source_table, dest_table
                        )
                        # Создаем копию dest_info, чтобы не изменять оригинальный
                        updated_dest_info = dest_info.copy()
                        updated_dest_info["columns"] = similar_fields
                        # Обновляем копию job, в которую вставляем обновленный dest_info
                        updated_job = job.copy()
                        updated_job["destination"] = updated_dest_info
                        print(
                            f"DEBUG: Set destination columns for job with table '{current_source_table}' -> '{dest_table}': {similar_fields}")
                        job = updated_job
                        dest_info = updated_dest_info  # Обновляем переменную для последующего использования
                    else:
                        print(
                            f"DEBUG: Source table '{current_source_table}' not found in source_schema. Cannot infer destination columns.")
                else:
                    print(
                        f"DEBUG: Destination table '{dest_table}' not found in dest_schema. Cannot infer destination columns.")
            else:
                print(
                    f"DEBUG: No source table found to infer destination columns for destination table '{dest_table}'.")

        # Если в destination нет 'key_fields'
        if "key_fields" not in dest_info or not dest_info["key_fields"]:
            if dest_schema and dest_table in dest_schema:
                primary_keys = self._get_primary_key_fields(dest_schema, dest_table)
                # Обновляем dest_info
                updated_dest_info = dest_info.copy()
                updated_dest_info["key_fields"] = primary_keys
                # Обновляем копию job, в которую вставляем обновленный dest_info
                updated_job = job.copy()
                updated_job["destination"] = updated_dest_info
                print(f"DEBUG: Set destination key_fields for table '{dest_table}': {primary_keys}")
                job = updated_job
            else:
                print(f"DEBUG: Destination table '{dest_table}' not found in dest_schema. Cannot infer key_fields.")

        # Возвращаем job, который мог быть оригиналом или копией, в зависимости от изменений
        return job


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
        # Создаем экземпляр ConfigManager для доступа к вспомогательным методам
        config_manager = cls()

        # Создаем копию конфига для модификации
        new_config = user_config.copy()

        # Обрабатываем каждый job в массиве jobs
        transformed_jobs = []
        for job in user_config.get("jobs", []):
            # Проверяем наличие ключа tables
            if "tables" in job:
                # Если есть ключ tables, используем add-jobs-from-tbl-names
                table_names = job["tables"]
                new_jobs = config_manager._add_jobs_from_tbl_names(table_names, source_schema, dest_schema)
                transformed_jobs.extend(new_jobs)
            else:
                # Обрабатываем обычный job с помощью нового метода
                processed_job = config_manager._transform_single_job(job, source_schema, dest_schema)
                transformed_jobs.append(processed_job)

        # Заменяем jobs в новом конфиге
        new_config["jobs"] = transformed_jobs

        return new_config