# main.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import logging  # Добавляем импорт модуля logging
from config_manager import ConfigManager
from job_manager import JobManager
from data_sources import SQLDataSource, MySqlDataSource, CSVDataSource
import sys

# todo сделать пользовательское форматирование , после выборки и перед изменениями

# Настройка логирования для main модуля (и всех модулей, использующих logging)
# Уровень можно установить на DEBUG, если нужно видеть все логи из data_transfer
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class TextHandler(logging.Handler):
    """Класс-обработчик для направления сообщений logging в виджет tkinter Text."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        """Вызывается, когда логгер получает сообщение."""
        msg = self.format(record)
        # Добавляем сообщение в конец текстового поля
        self.text_widget.insert(tk.END, msg + '\n')
        # Прокручиваем вниз, чтобы видеть последние сообщения
        self.text_widget.see(tk.END)
        # Обновляем GUI
        self.text_widget.update_idletasks()

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

        # Определите список вкладок: (имя_атрибута_фрейма, текст_вкладки, имя_метода_настройки)
        tabs_config = [
            ("config_frame", "Configuration", "setup_config_tab"),
            ("source_schema_frame", "Source Schema", "setup_source_schema_tab"),
            ("dest_schema_frame", "Destination Schema", "setup_dest_schema_tab"),
            ("table_preview", "Table", "setup_load_data_tab"),
            ("log_frame", "Logs", "setup_log_tab"),
            ("execution_frame", "Execution", "setup_execution_tab"),
        ]

        # --- НАЧАЛО ИЗМЕНЕНИЙ ---
        # Создаем все фреймы и настраиваем вкладки
        for frame_attr, tab_text, setup_method_name in tabs_config:
            frame = ttk.Frame(self.notebook)
            setattr(self, frame_attr, frame)
            self.notebook.add(frame, text=tab_text)
            setup_method = getattr(self, setup_method_name)
            setup_method()  # Вызываем setup_log_tab тоже

        # После того, как self.log_text создан в setup_log_tab,
        # настраиваем logging, чтобы оно использовало это поле
        # Очищаем все существующие обработчики у корневого логгера (если были из basicConfig)
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Устанавливаем уровень корневого логгера (например, DEBUG)
        root_logger.setLevel(logging.DEBUG)

        # Создаем наш кастомный TextHandler
        text_handler = TextHandler(self.log_text)
        # Устанавливаем формат для сообщений
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        text_handler.setFormatter(formatter)

        # Добавляем обработчик к корневому логгеру
        root_logger.addHandler(text_handler)

        # Также можно добавить обработчик в консоль, если нужно дублировать
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # Загрузка конфига по умолчанию
        self.load_default_config_at_startup()

    def load_default_config_at_startup(self):
        """
        Пытается загрузить конфигурацию из файла 'default.json' при запуске приложения.
        Если файл не найден или содержит ошибки, используется конфигурация по умолчанию.
        """
        default_config_path = "default.json"
        try:
            # Пытаемся загрузить конфиг из файла default.json
            self.config_manager.load_config(default_config_path)
            # Обновляем текстовое поле конфигурации
            self.config_text.delete(1.0, tk.END)
            self.config_text.insert(1.0, json.dumps(self.config_manager.get_config(), indent=2))
            self.log_message(f"Configuration loaded from: {default_config_path}")
            self.logger.info(f"Configuration loaded from: {default_config_path}")
        except FileNotFoundError:
            self.logger.warning(f"File {default_config_path} not found. Loading default config.")
            self.log_message(f"File {default_config_path} not found. Loading default config.")
            # Если файл не найден, загружаем конфигурацию по умолчанию
            self.new_config()
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in {default_config_path}: {e}. Loading default config.")
            self.log_message(f"Invalid JSON in {default_config_path}. Loading default config.")
            # Если JSON некорректен, загружаем конфигурацию по умолчанию
            self.new_config()
        except Exception as e:
            self.logger.error(f"Unexpected error loading {default_config_path}: {e}. Loading default config.")
            self.log_message(f"Error loading {default_config_path}. Loading default config.")
            # На всякий случай, если возникнет другая ошибка, также загружаем конфигурацию по умолчанию
            self.new_config()


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

        # Примечание: Загрузка начального конфига теперь происходит в load_default_config_at_startup
        # Поэтому вызов self.new_config() здесь больше не нужен, если мы хотим сначала попытаться загрузить default.json


    # ... (остальные методы остаются без изменений, включая setup_source_schema_tab, setup_dest_schema_tab,
    # setup_execution_tab, setup_log_tab, setup_load_data_tab, log_message, load_config, save_config,
    # new_config, load_source_schema, load_dest_schema, display_schema, load_from_table, load_data,
    # run_transfer, stop_transfer) ...

    def setup_schema_tab(self, frame_attr, button_text, command):
        """
        Вспомогательный метод для настройки вкладок схемы (источник и приемник).

        :param frame_attr: Атрибут экземпляра класса, содержащий фрейм вкладки (например, 'source_schema_frame')
        :param button_text: Текст для кнопки загрузки схемы
        :param command: Команда (функция), привязанная к кнопке загрузки
        :return: Объект Treeview, созданный для вкладки
        """
        # Получаем фрейм вкладки
        frame = getattr(self, frame_attr)

        # Кнопка загрузки схемы
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text=button_text, command=command).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Load from Table", command=self.load_from_table).pack(side=tk.LEFT, padx=2)

        # Дерево для отображения схемы
        tree = ttk.Treeview(frame)
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Определяем колонки
        tree["columns"] = ("Type", "Details")
        tree.column("#0", width=150, minwidth=100)
        tree.column("Type", width=100, minwidth=80)
        tree.column("Details", width=300, minwidth=150)

        # Заголовки колонок
        tree.heading("#0", text="Name")
        tree.heading("Type", text="Type")
        tree.heading("Details", text="Details")

        return tree

    def setup_source_schema_tab(self):
        # Настройка вкладки схемы источника
        self.source_schema_tree = self.setup_schema_tab(
            frame_attr="source_schema_frame",
            button_text="Load Source Schema",
            command=self.load_source_schema
        )

    def setup_dest_schema_tab(self):
        # Настройка вкладки схемы приемника
        self.dest_schema_tree = self.setup_schema_tab(
            frame_attr="dest_schema_frame",
            button_text="Load Destination Schema",
            command=self.load_dest_schema
        )

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

        # метка
        btn_frame = ttk.Frame(self.table_preview)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        self.table_name_label = ttk.Label(btn_frame, text="Table Name:")
        self.table_name_label.pack(side=tk.LEFT, padx=(0, 5))

        # Область для отображения данных
        data_frame = ttk.LabelFrame(self.table_preview, text="Data Preview (First 10 rows)")
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
                "type": "csv",
                "connection_params": {
                    "path": "test.csv"
                },
                "query": "test.csv",
                "columns": ["product_id", "model", "date_added"],
                "filters": {}
            },
            "destination": {
                "type": "sql",
                "connection_params": {
                    "path": "test.db"
                },
                "table": "oc_product",
                "columns": ["product_id", "model", "date_added"]
            },
            "transformation": {
                "source_path": "",
                "destination_path": ""
            },
            "comparison": {
                "key_fields": ["product_id"] # Исправлено: было ["id"]
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


        connection_params = source_config.get("connection_params", {})

        # Создаем экземпляр соответствующего источника данных
        if source_type == "mysql":
            source = MySqlDataSource(connection_params)
        if source_type == "sql":
            source = SQLDataSource(connection_params)
        if source_type == "csv":
            source = CSVDataSource(connection_params)
        try:
            source.connect()
            schema = source.get_schema()
            source.disconnect()

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


        connection_params = dest_config.get("connection_params", {})

        # Создаем экземпляр соответствующего источника данных
        if dest_type == "mysql":
            destination = MySqlDataSource(connection_params)
        if dest_type == "sql":
            destination = SQLDataSource(connection_params)
        if dest_type == "csv":
            destination = CSVDataSource(connection_params)
        try:
            destination.connect()
            schema = destination.get_schema()
            destination.disconnect()

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

    def load_from_table(self):
        # Проверяем, какая вкладка схемы сейчас активна
        current_tab_window = self.notebook.nametowidget(self.notebook.select())

        # Определяем, какое дерево использовать и какую функцию загрузки вызвать
        if current_tab_window == self.source_schema_frame:
            tree = self.source_schema_tree
            schema_type = "source"
        elif current_tab_window == self.dest_schema_frame:
            tree = self.dest_schema_tree
            schema_type = "destination"
        else:
            messagebox.showwarning("Warning", "Please select a table from the Source or Destination Schema tab")
            return

        # Получаем выделенный элемент в соответствующем дереве
        selected_item = tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select a table from the schema tree")
            return

        # Получаем текст (имя) выделенного элемента
        item_text = tree.item(selected_item[0], "text")

        # Проверяем, является ли элемент таблицей (а не колонкой)
        parent_id = tree.parent(selected_item[0])
        if parent_id != "":  # Это колонка, а не таблица
            # Находим родительский элемент (таблицу)
            table_name = tree.item(parent_id, "text")
        else:  # Это таблица
            table_name = item_text

        # Заполняем поле ввода имени таблицы на вкладке Load Data
        self.table_name_label.config(text=f"Table: {table_name} from {schema_type}")

        # Переключаемся на вкладку Load Data
        self.notebook.select(self.table_preview)

        # Вызываем универсальный метод загрузки данных с указанным именем таблицы и типом схемы
        self.load_data(table_name, schema_type=schema_type)

    def load_data(self, table_name=None, schema_type=None):
        """
        Загружает первые 10 строк из указанной таблицы из источника или приемника.

        :param table_name: Имя таблицы для загрузки. Если None, берется из self.table_name_entry.
        :param schema_type: "source" или "destination". Определяет, откуда загружать данные.
                            Если None, по умолчанию "source".
        """
        if table_name is None:
            table_name = self.table_name_entry.get().strip()
        if not table_name:
            messagebox.showwarning("Warning", "Please enter a table name")
            return

        # Если schema_type не указан, по умолчанию загружаем из источника
        if schema_type is None:
            schema_type = "source"

        # Выбираем конфигурацию в зависимости от типа схемы
        config_key = "source" if schema_type == "source" else "destination"
        connection_config_key = f"{schema_type}_connection_params"  # Для логов

        try:
            config_content = self.config_text.get(1.0, tk.END)
            config = json.loads(config_content)
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON in configuration editor")
            return

        # Получаем конфигурацию для указанного типа (source или destination)
        db_config = config.get(config_key, {})
        db_type = db_config.get("type", "")


        connection_params = db_config.get("connection_params", {})

        # Создаем экземпляр соответствующего источника данных
        if db_type == "mysql":
            source = MySqlDataSource(connection_params)
        if db_type == "sql":
            source = SQLDataSource(connection_params)
        if db_type == "csv":
            source = CSVDataSource(connection_params)

        try:
            source.connect()
            # Запрашиваем первые 10 строк из указанной таблицы
            query = f"SELECT * FROM {table_name} LIMIT 10"
            rows = source.fetch_data(query)

            # Вывод данных если не пусто
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

                self.log_message(f"Data loaded successfully from table '{table_name}' in {config_key} schema.")

            else:
                # Если данных нет
                # Очищаем Treeview
                for item in self.data_tree.get_children():
                    self.data_tree.delete(item)
                # Очищаем колонки
                self.data_tree["columns"] = ()
                self.data_tree["show"] = "tree"  # Показываем пустое дерево или просто ничего

                self.log_message(f"No data found in table '{table_name}' in {config_key} schema or table is empty.")

        except Exception as e:
            source.disconnect()  # Убедимся, что соединение закрыто при ошибке
            messagebox.showerror("Error", f"Failed to load data from {connection_config_key}: {str(e)}")
            self.log_message(f"Error loading data: {str(e)}")

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
            transfer = JobManager(config)
            transfer.run()

            # Обновляем счетчики после выполнения

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