# config_manager.py
import json
from typing import Any, Dict, List, Tuple
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog


# Класс для работы с конфигурацией
class ConfigManager:
    def __init__(self, config_file: str = None):
        self.config_file = config_file
        self.config = {
            "source": {
                "type": "sql",  # mysql, sql, csv, api
                "connection_params": {}
            },
            "destination": {
                "type": "sql",
                "connection_params": {}
            },
            "jobs": [
                {"source": {
                    "query": "",  # или table, для csv это путь файла
                    "columns": [],
                    "filters": {}
                },
                    "destination": {
                        "table": "",  # может быть query для сложной выборки, для csv это путь файла
                        "columns": []
                    },
                    "transformation": {
                        "source_path": "",
                        "destination_path": ""
                    },
                    "comparison": {
                        "key_fields": []
                    }

                },
                {"source": {  # может быть без фильтров и таблиц
                    "query": "",
                },
                    "destination": {
                        "query": "",  # для выборки и сравнения с source
                        "table": "",  # для обновления полученными данными
                        "columns": []
                    },
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

    def _get_similar_fields(self, source_schema: Dict[str, List[str]], dest_schema: Dict[str, List[str]],
                            source_table: str, dest_table: str) -> List[str]:
        """
        Вспомогательный метод для получения списка одинаковых полей из двух таблиц

        Args:
            source_schema: Словарь схемы источника {table_name: [column_list]}
            dest_schema: Словарь схемы назначения {table_name: [column_list]}
            source_table: Имя таблицы в источнике
            dest_table: Имя таблицы в назначении

        Returns:
            List[str]: Список одинаковых полей
        """
        source_columns = set(source_schema.get(source_table, []))
        dest_columns = set(dest_schema.get(dest_table, []))
        return list(source_columns.intersection(dest_columns))

    def _add_jobs_from_tbl_names(self, table_names: List[str], source_schema: Dict[str, List[str]],
                                 dest_schema: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """
        Вспомогательный метод для создания новых заданий из списка имен таблиц

        Args:
            table_names: Список имен таблиц
            source_schema: Словарь схемы источника
            dest_schema: Словарь схемы назначения

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

            # Создаем новое задание
            job = {
                "source": {
                    "table": table_name,
                    "columns": similar_fields,
                    "filters": {}
                },
                "destination": {
                    "table": table_name,
                    "columns": similar_fields
                },
                "transformation": {
                    "source_path": "",
                    "destination_path": ""
                },
                "comparison": {
                    "key_fields": []
                }
            }
            new_jobs.append(job)

        return new_jobs

    def transform_config(self, user_config: Dict[str, Any], source_schema: Dict[str, List[str]],
                         dest_schema: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Метод для преобразования конфига на основе пользовательского конфига и схем баз данных

        Args:
            user_config: Пользовательский конфиг
            source_schema: Словарь схемы источника {table_name: [column_list]}
            dest_schema: Словарь схемы назначения {table_name: [column_list]}

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
                source_info = job.get("source", {})
                dest_info = job.get("destination", {})

                # Проверяем наличие table и query в source
                if source_info.get("table") and source_info.get("query"):
                    raise ValueError("Выборка данных из источника должна быть однозначной.")

                # Получаем информацию о таблицах
                source_table = source_info.get("table")
                dest_table = dest_info.get("table")

                # Если указана только одна таблица, присваиваем другой такое же имя
                if source_table and not dest_table:
                    dest_table = source_table
                    dest_info["table"] = dest_table
                elif dest_table and not source_table:
                    source_table = dest_table
                    source_info["table"] = source_table
                elif not dest_table:
                    # Если нет dest_table, выдаем ошибку
                    raise ValueError(f"Должна быть таблица в приемнике для обновления в ней данных. Источник - {source_table} , приемник - {dest_table}")

                # Проверяем наличие columns в source и destination
                source_columns = source_info.get("columns")
                dest_columns = dest_info.get("columns")

                # Если есть имена таблиц и полей в source и destination, оставляем как есть
                if source_table and dest_table and source_columns is not None and dest_columns is not None:
                    transformed_jobs.append(job)
                    continue

                # Если есть columns только у одной таблицы, копируем в другую
                if source_columns is not None and dest_columns is None:
                    dest_info["columns"] = source_columns
                elif dest_columns is not None and source_columns is None:
                    source_info["columns"] = dest_columns
                # Если нет columns у обоих, получаем их из схем
                elif source_columns is None and dest_columns is None:
                    if source_table and dest_table:
                        similar_fields = self._get_similar_fields(source_schema, dest_schema, source_table, dest_table)
                        if not similar_fields:
                            raise ValueError(f"У таблиц '{source_table}' и '{dest_table}' нет одинаковых полей")
                        source_info["columns"] = similar_fields
                        dest_info["columns"] = similar_fields
                    else:
                        # Если таблицы не указаны, оставляем пустой список
                        source_info["columns"] = []
                        dest_info["columns"] = []

                # Обновляем job
                updated_job = job.copy()
                updated_job["source"] = source_info
                updated_job["destination"] = dest_info
                transformed_jobs.append(updated_job)

        # Обновляем jobs в новом конфиге
        new_config["jobs"] = transformed_jobs

        return new_config