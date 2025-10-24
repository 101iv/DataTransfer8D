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

    def transform_config(self, user_config: Dict[str, Any], source_schema: Dict[str, List[Dict[str, Any]]],
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
        # Создаем копию конфига для модификации
        new_config = user_config.copy()

        # Обрабатываем каждый job в массиве jobs
        transformed_jobs = []
        for job in user_config.get("jobs", []):
            # Проверяем наличие ключа tables
            if "tables" in job:
                # Если есть ключ tables, используем add-jobs-from-tbl-names
                table_names = job["tables"]
                new_jobs = self._add_jobs_from_tbl_names(table_names, source_schema, dest_schema)
                transformed_jobs.extend(new_jobs)
            else:
                # Обрабатываем обычный job
                # Оставляем job без изменений, он уже содержит source, destination и transformation
                # Ключи сравнения будут искаться внутри DataTransfer по мере выполнения конкретного job
                transformed_jobs.append(job)

        # Заменяем jobs в новом конфиге
        new_config["jobs"] = transformed_jobs

        return new_config