# config_manager.py
import json
from typing import Any, Dict
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog


# Класс для работы с конфигурацией
class ConfigManager:
    def __init__(self, config_file: str = None):
        self.config_file = config_file
        self.config = {
            "source": {
                "type": "sql",  # sql, csv, api
                "connection_params": {},
                "query": "",
                "columns": [],
                "filters": {}
            },
            "destination": {
                "type": "sql",
                "connection_params": {},
                "table": "",
                "columns": []
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
                "key_fields": []
            }
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