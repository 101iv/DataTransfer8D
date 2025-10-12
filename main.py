# main.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
from config_manager import ConfigManager
from data_transfer import DataTransfer
from data_sources import SQLDataSource


# GUI приложение
class DataTransferApp:
    def __init__(self, root):
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

        # Вкладка выполнения
        self.execution_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.execution_frame, text="Execution")
        self.setup_execution_tab()

        # Вкладка логов
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="Logs")
        self.setup_log_tab()

    def setup_config_tab(self):
        # Кнопки управления конфигурацией
        btn_frame = ttk.Frame(self.config_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Load Config", command=self.load_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Save Config", command=self.save_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="New Config", command=self.new_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Load Schema", command=self.load_schema).pack(side=tk.RIGHT, padx=2)

        # Панель для редактирования конфигурации
        self.config_text = scrolledtext.ScrolledText(self.config_frame, wrap=tk.WORD)
        self.config_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Загружаем пример конфигурации
        self.new_config()

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
            "formatting": {
                "source_format": {},
                "destination_format": {}
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

    def load_schema(self):
        try:
            config_content = self.config_text.get(1.0, tk.END)
            config = json.loads(config_content)
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON in configuration editor")
            return

        source_type = config.get("source", {}).get("type", "")
        if source_type != "sql":
            messagebox.showwarning("Warning", "Schema loading is only supported for SQL sources")
            return

        connection_params = config.get("source", {}).get("connection_params", {})
        source = SQLDataSource(connection_params)

        try:
            source.connect()
            schema = source.get_schema()
            source.disconnect()

            # Обновляем конфигурацию с новой схемой
            config["source"]["schema"] = schema
            self.config_text.delete(1.0, tk.END)
            self.config_text.insert(1.0, json.dumps(config, indent=2))

            self.log_message("Schema loaded successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load schema: {str(e)}")

    def run_transfer(self):
        try:
            config_content = self.config_text.get(1.0, tk.END)
            config = json.loads(config_content)
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON in configuration editor")
            return

        self.log_message("Starting data transfer...")
        self.progress['value'] = 0

        try:
            transfer = DataTransfer(config)
            transfer.fetch_data()
            self.log_message("Data fetched successfully")

            transfer.format_data()
            self.log_message("Data formatted successfully")

            transfer.transform_data()
            self.log_message("Data transformed successfully")

            transfer.compare_data()
            self.log_message("Data comparison completed")

            # Обновляем счетчики
            self.insert_count.config(text=str(len(transfer.to_insert)))
            self.update_count.config(text=str(len(transfer.to_update)))
            self.delete_count.config(text=str(len(transfer.to_delete)))

            transfer.modify_data()
            self.log_message("Data modifications applied")

            transfer.execute_changes()
            self.log_message("Changes executed successfully")

            self.progress['value'] = 100
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(1.0, f"Transfer completed:\n")
            self.result_text.insert(tk.END, f"- {len(transfer.to_insert)} records inserted\n")
            self.result_text.insert(tk.END, f"- {len(transfer.to_update)} records updated\n")
            self.result_text.insert(tk.END, f"- {len(transfer.to_delete)} records deleted\n")

        except Exception as e:
            self.log_message(f"Error during transfer: {str(e)}")
            messagebox.showerror("Error", f"Transfer failed: {str(e)}")

    def stop_transfer(self):
        self.log_message("Transfer stopped by user")
        self.progress['value'] = 0


if __name__ == "__main__":
    root = tk.Tk()
    app = DataTransferApp(root)
    root.mainloop()