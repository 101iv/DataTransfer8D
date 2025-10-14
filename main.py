# main.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import logging  # Добавляем импорт модуля logging
from config_manager import ConfigManager
from data_transfer import DataTransfer
from data_sources import SQLDataSource, MySqlDataSource

# todo сделать пользовательское форматирование и примеры конфига для разных источников

# Настройка логирования для main модуля (и всех модулей, использующих logging)
# Уровень можно установить на DEBUG, если нужно видеть все логи из data_transfer
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# GUI приложение
class DataTransferApp:
    def __init__(self, root):
        self.logger = logging.getLogger(__name__) # Создаем логгер для этого класса
        self.logger.info("Инициализация DataTransferApp")
        self.root = root
        self.root.title("Data Transfer Tool")
        self.root.geometry("1000x700")
        self.config_manager = ConfigManager()
        # Создаем вкладки
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Вкладка конфигурации
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Configuration")
        self.setup_config_tab()

        # Вкладка схемы источника
        self.source_schema_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.source_schema_frame, text="Source Schema")
        self.setup_source_schema_tab()

        # Вкладка схемы приемника
        self.dest_schema_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dest_schema_frame, text="Destination Schema")
        self.setup_dest_schema_tab()

        # Вкладка выполнения
        self.execution_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.execution_frame, text="Execution")
        self.setup_execution_tab()

        # Вкладка логов
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="Logs")
        self.setup_log_tab()

        # Вкладка Load Data
        self.load_data_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.load_data_frame, text="Load Data")
        self.setup_load_data_tab()

    def setup_config_tab(self):
        # Кнопки управления конфигурацией
        btn_frame = ttk.Frame(self.config_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Load Config", command=self.load_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Save Config", command=self.save_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="New Config", command=self.new_config).pack(side=tk.LEFT, padx=2)

        # Панель для редактирования конфигурации
        self.config_text = scrolledtext.ScrolledText(self.config_frame, wrap=tk.WORD)
        self.config_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Загружаем пример конфигурации
        self.new_config()

    def setup_source_schema_tab(self):
        # Кнопка загрузки схемы источника
        load_source_btn = ttk.Button(self.source_schema_frame, text="Load Source Schema",
                                     command=self.load_source_schema)
        load_source_btn.pack(side=tk.TOP, pady=5)

        # Кнопка для загрузки данных из выделенной таблицы
        load_data_from_table_btn = ttk.Button(self.source_schema_frame, text="Load Data from Selected Table",
                                              command=self.load_data_from_selected_table)
        load_data_from_table_btn.pack(side=tk.TOP, pady=5)

        # Дерево для отображения схемы источника
        self.source_schema_tree = ttk.Treeview(self.source_schema_frame)
        self.source_schema_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Определяем колонки
        self.source_schema_tree["columns"] = ("Type", "Details")
        self.source_schema_tree.column("#0", width=150, minwidth=100)
        self.source_schema_tree.column("Type", width=100, minwidth=80)
        self.source_schema_tree.column("Details", width=300, minwidth=150)

        # Заголовки колонок
        self.source_schema_tree.heading("#0", text="Name")
        self.source_schema_tree.heading("Type", text="Type")
        self.source_schema_tree.heading("Details", text="Details")

    def setup_dest_schema_tab(self):
        # Кнопка загрузки схемы приемника
        load_dest_btn = ttk.Button(self.dest_schema_frame, text="Load Destination Schema",
                                   command=self.load_dest_schema)
        load_dest_btn.pack(side=tk.TOP, pady=5)

        # Дерево для отображения схемы приемника
        self.dest_schema_tree = ttk.Treeview(self.dest_schema_frame)
        self.dest_schema_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Определяем колонки
        self.dest_schema_tree["columns"] = ("Type", "Details")
        self.dest_schema_tree.column("#0", width=150, minwidth=100)
        self.dest_schema_tree.column("Type", width=100, minwidth=80)
        self.dest_schema_tree.column("Details", width=300, minwidth=150)

        # Заголовки колонок
        self.dest_schema_tree.heading("#0", text="Name")
        self.dest_schema_tree.heading("Type", text="Type")
        self.dest_schema_tree.heading("Details", text="Details")

    def setup_execution_tab(self):
        # Кнопки управления выполнением
        btn_frame = ttk.Frame(self.execution_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Run Transfer", command=self.run_transfer).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Stop", command=self.stop_transfer).pack(side=tk.LEFT, padx=2)

        # Прогресс бар
        self.progress = ttk.Progressbar(btn_frame, mode='determinate')
        self.progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        # Информационная панель
        info_frame = ttk.LabelFrame(self.execution_frame, text="Transfer Information")
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(info_frame, text="Records to Insert:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.insert_count = ttk.Label(info_frame, text="0")
        self.insert_count.grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(info_frame, text="Records to Update:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.update_count = ttk.Label(info_frame, text="0")
        self.update_count.grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(info_frame, text="Records to Delete:").grid(row=0, column=4, sticky=tk.W, padx=5)
        self.delete_count = ttk.Label(info_frame, text="0")
        self.delete_count.grid(row=0, column=5, sticky=tk.W, padx=5)

        # Результаты выполнения
        result_frame = ttk.LabelFrame(self.execution_frame, text="Results")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def setup_log_tab(self):
        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def setup_load_data_tab(self):
        # Кнопка загрузки данных
        load_data_btn = ttk.Button(self.load_data_frame, text="Load Data", command=self.load_data)
        load_data_btn.pack(side=tk.TOP, pady=5)

        # Поле для ввода имени таблицы
        table_input_frame = ttk.Frame(self.load_data_frame)
        table_input_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(table_input_frame, text="Table Name:").pack(side=tk.LEFT, padx=(0, 5))
        self.table_name_entry = ttk.Entry(table_input_frame)
        self.table_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Область для отображения данных
        data_frame = ttk.LabelFrame(self.load_data_frame, text="Data Preview (First 10 rows)")
        data_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Создаем Treeview для отображения данных
        self.data_tree = ttk.Treeview(data_frame)
        self.data_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Добавляем вертикальный скроллбар
        v_scrollbar = ttk.Scrollbar(data_frame, orient="vertical", command=self.data_tree.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)
        self.data_tree.configure(yscrollcommand=v_scrollbar.set)

        # Добавляем горизонтальный скроллбар
        h_scrollbar = ttk.Scrollbar(data_frame, orient="horizontal", command=self.data_tree.xview)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0, 5))
        self.data_tree.configure(xscrollcommand=h_scrollbar.set)

    def log_message(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def load_config(self):
        file_path = filedialog.askopenfilename(
            title="Select Configuration File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                self.config_manager.load_config(file_path)
                self.config_text.delete(1.0, tk.END)
                self.config_text.insert(1.0, json.dumps(self.config_manager.get_config(), indent=2))
                self.log_message(f"Configuration loaded from: {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")

    def save_config(self):
        try:
            config_content = self.config_text.get(1.0, tk.END)
            config = json.loads(config_content)
            self.config_manager.set_config(config)
            self.config_manager.save_config()
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON in configuration editor")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

    def new_config(self):
        default_config = {
            "source": {
                "type": "sql",
                "connection_params": {
                    "path": "source.db"
                },
                "query": "SELECT * FROM source_table",
                "columns": ["id", "name", "value"],
                "filters": {}
            },
            "destination": {
                "type": "sql",
                "connection_params": {
                    "path": "destination.db"
                },
                "table": "destination_table",
                "columns": ["id", "name", "value"]
            },
            "transformation": {
                "source_path": "",
                "destination_path": ""
            },
            "comparison": {
                "key_fields": ["id"]
            }
        }
        self.config_manager.set_config(default_config)
        self.config_text.delete(1.0, tk.END)
        self.config_text.insert(1.0, json.dumps(default_config, indent=2))

    def load_source_schema(self):
        try:
            config_content = self.config_text.get(1.0, tk.END)
            config = json.loads(config_content)
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON in configuration editor")
            return

        source_config = config.get("source", {})
        source_type = source_config.get("type", "")
        if source_type not in ["sql", "mysql"]:
            messagebox.showwarning("Warning", "Schema loading is only supported for SQL sources")
            return

        connection_params = source_config.get("connection_params", {})

        # Создаем экземпляр соответствующего источника данных
        if source_type == "mysql":
            source = MySqlDataSource(connection_params)
        else:  # sql
            source = SQLDataSource(connection_params)

        try:
            source.connect()
            schema = source.get_schema()
            source.disconnect()

            # Обновляем конфигурацию с новой схемой
            config["source"]["schema"] = schema
            self.config_text.delete(1.0, tk.END)
            self.config_text.insert(1.0, json.dumps(config, indent=2))

            # Отображаем схему во вкладке Source Schema
            self.display_schema(self.source_schema_tree, schema)

            self.log_message("Source schema loaded successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load source schema: {str(e)}")

    def load_dest_schema(self):
        try:
            config_content = self.config_text.get(1.0, tk.END)
            config = json.loads(config_content)
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON in configuration editor")
            return

        dest_config = config.get("destination", {})
        dest_type = dest_config.get("type", "")
        if dest_type not in ["sql", "mysql"]:
            messagebox.showwarning("Warning", "Schema loading is only supported for SQL destinations")
            return

        connection_params = dest_config.get("connection_params", {})

        # Создаем экземпляр соответствующего источника данных
        if dest_type == "mysql":
            destination = MySqlDataSource(connection_params)
        else:  # sql
            destination = SQLDataSource(connection_params)

        try:
            destination.connect()
            schema = destination.get_schema()
            destination.disconnect()

            # Обновляем конфигурацию с новой схемой
            config["destination"]["schema"] = schema
            self.config_text.delete(1.0, tk.END)
            self.config_text.insert(1.0, json.dumps(config, indent=2))

            # Отображаем схему во вкладке Destination Schema
            self.display_schema(self.dest_schema_tree, schema)

            self.log_message("Destination schema loaded successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load destination schema: {str(e)}")

    def display_schema(self, tree_widget, schema):
        # Очищаем дерево
        for item in tree_widget.get_children():
            tree_widget.delete(item)

        # Заполняем дерево схемой
        for table_name, columns in schema.items():
            # Добавляем таблицу как родительский элемент
            table_id = tree_widget.insert("", "end", text=table_name, values=("Table", f"{len(columns)} columns"))

            # Добавляем колонки как дочерние элементы
            for col_info in columns:
                col_name = col_info["name"]
                col_type = col_info["type"]
                extra_info = []

                if col_info.get("not_null"):
                    extra_info.append("NOT NULL")
                if col_info.get("primary_key"):
                    extra_info.append("PK")
                if col_info.get("default") is not None:
                    extra_info.append(f"DEFAULT: {col_info['default']}")

                extra_str = ", ".join(extra_info) if extra_info else ""

                tree_widget.insert(
                    table_id,
                    "end",
                    text=col_name,
                    values=("Column", f"{col_type} {extra_str}".strip())
                )

    def load_data_from_selected_table(self):
        # Получаем выделенный элемент в дереве схемы источника
        selected_item = self.source_schema_tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select a table from the schema tree")
            return

        # Получаем текст (имя) выделенного элемента
        table_name = self.source_schema_tree.item(selected_item[0], "text")

        # Проверяем, является ли элемент таблицей (а не колонкой)
        parent_id = self.source_schema_tree.parent(selected_item[0])
        if parent_id != "":  # Это колонка, а не таблица
            # Находим родительский элемент (таблицу)
            table_name = self.source_schema_tree.item(parent_id, "text")

        # Заполняем поле ввода имени таблицы на вкладке Load Data
        self.table_name_entry.delete(0, tk.END)
        self.table_name_entry.insert(0, table_name)

        # Переключаемся на вкладку Load Data
        self.notebook.select(self.load_data_frame)

        # Вызываем метод загрузки данных с указанным именем таблицы
        self.load_data(table_name)

    def load_data(self, table_name=None):
        if table_name is None:
            table_name = self.table_name_entry.get().strip()
        if not table_name:
            messagebox.showwarning("Warning", "Please enter a table name")
            return

        try:
            config_content = self.config_text.get(1.0, tk.END)
            config = json.loads(config_content)
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON in configuration editor")
            return

        # Пытаемся определить источник данных из конфига
        source_config = config.get("source", {})
        source_type = source_config.get("type", "")
        if source_type not in ["sql", "mysql"]:
            messagebox.showwarning("Warning", "Data loading is only supported for SQL sources")
            return

        connection_params = source_config.get("connection_params", {})

        # Создаем экземпляр соответствующего источника данных
        if source_type == "mysql":
            source = MySqlDataSource(connection_params)
        else:  # sql
            source = SQLDataSource(connection_params)

        try:
            source.connect()
            # Запрашиваем первые 10 строк из указанной таблицы
            query = f"SELECT * FROM {table_name} LIMIT 10"
            rows = source.fetch_data(query)

            # вывод данных если не пусто
            if rows:
                columns = list(rows[0].keys())

                source.disconnect()

                # Очищаем предыдущие данные в Treeview
                for item in self.data_tree.get_children():
                    self.data_tree.delete(item)

                # Определяем колонки Treeview
                self.data_tree["columns"] = columns
                self.data_tree["show"] = "headings"  # Показываем только заголовки

                # Настройка заголовков и ширины колонок
                for col in columns:
                    self.data_tree.heading(col, text=col)
                    self.data_tree.column(col, width=100, minwidth=50)

                # Вставка данных
                for row in rows:
                    values = [row[col] for col in columns]
                    self.data_tree.insert("", "end", values=values)

                self.log_message(f"Data loaded successfully from table: {table_name}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load  {str(e)}")

    def run_transfer(self):
        self.logger.info("--- ЗАПУСК ПЕРЕНОСА ИЗ GUI ---")  # Используем self.logger
        # logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Убираем эту строку из run_transfer, так как basicConfig уже вызван
        try:
            config_content = self.config_text.get(1.0, tk.END)
            config = json.loads(config_content)
        except json.JSONDecodeError:
            self.logger.error("Ошибка: Неверный JSON в редакторе конфигурации.")  # Используем self.logger
            messagebox.showerror("Error", "Invalid JSON in configuration editor")
            return

        self.log_message("Starting data transfer...")
        self.progress['value'] = 0
        try:
            transfer = DataTransfer(config)
            transfer.run()  # Теперь все логи из data_transfer должны появиться в консоли

            # Обновляем счетчики после выполнения
            # (transfer.compare_data() уже вызван внутри transfer.run())
            self.insert_count.config(text=str(len(transfer.to_insert)))
            self.update_count.config(text=str(len(transfer.to_update)))
            self.delete_count.config(text=str(len(transfer.to_delete)))

            self.progress['value'] = 100
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(1.0, f"Transfer completed successfully:\n")
            self.result_text.insert(tk.END, f"- {len(transfer.to_insert)} records inserted\n")
            self.result_text.insert(tk.END, f"- {len(transfer.to_update)} records updated\n")
            self.result_text.insert(tk.END, f"- {len(transfer.to_delete)} records deleted\n")
            self.logger.info("--- ПЕРЕНОС ЗАВЕРШЕН УСПЕШНО ИЗ GUI ---")  # Используем self.logger
        except Exception as e:
            self.logger.error(f"--- ПЕРЕНОС ЗАВЕРШЕН С ОШИБКОЙ ИЗ GUI: {e} ---")  # Используем self.logger
            self.log_message(f"Error during transfer: {e}")
            messagebox.showerror("Error", f"Transfer failed: {e}")

    def stop_transfer(self):
        self.log_message("Transfer stopped by user")
        self.progress['value'] = 0


if __name__ == "__main__":
    root = tk.Tk()
    app = DataTransferApp(root)
    root.mainloop()