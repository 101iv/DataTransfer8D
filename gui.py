# gui.py
import json
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTextEdit, QPushButton, QFrame, QProgressBar, QLabel,
    QSizePolicy, QSpacerItem,
    QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QGroupBox, QSplitter, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class DataTransferGUI(QMainWindow):
    """
    Класс, отвечающий за GUI.
    """

    def __init__(self, logic):
        super().__init__()
        self.logic = logic
        self.selected_table = {"source": None, "destination": None}
        self.selected_schema_type = "source"  # По умолчанию источник

        self.setWindowTitle("Data Transfer Tool")
        self.setGeometry(100, 100, 1200, 800)

        # Установка шрифта для всего окна
        font = QFont()
        font.setPointSize(10)  # Увеличенный размер шрифта
        self.setFont(font)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Вкладки
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Инициализация вкладок
        self.init_config_tab()
        self.init_transformed_config_tab()
        self.init_source_schema_tab()
        self.init_dest_schema_tab()
        self.init_table_preview_tab()
        self.init_log_tab()
        self.init_execution_tab()

        # Загрузка конфига по умолчанию
        self.load_default_config_at_startup()

    def create_standard_button(self, text, callback):
        """Создает кнопку с общим стилем."""
        btn = QPushButton(text)
        btn.clicked.connect(callback)
        # Установка фиксированного размера
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn.setFixedWidth(150) # Установка фиксированной ширины
        # Можно также установить фиксированную высоту, если нужно
        btn.setFixedHeight(30)
        return btn

    def init_config_tab(self):
        self.config_frame = QWidget()
        layout = QVBoxLayout(self.config_frame)

        btn_layout = QHBoxLayout()
        self.load_config_btn = self.create_standard_button("Load Config", self.load_config)
        self.save_config_btn = self.create_standard_button("Save Config", self.save_config)
        self.new_config_btn = self.create_standard_button("New Config", self.new_config)

        btn_layout.addWidget(self.load_config_btn)
        btn_layout.addWidget(self.save_config_btn)
        btn_layout.addWidget(self.new_config_btn)
        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

        self.config_text = QTextEdit()
        layout.addWidget(self.config_text)

        self.tabs.addTab(self.config_frame, "Configuration")

    def init_transformed_config_tab(self):
        self.transformed_config_frame = QWidget()
        layout = QVBoxLayout(self.transformed_config_frame)

        btn_layout = QHBoxLayout()
        self.transform_config_btn = self.create_standard_button("Transform Config", self.transform_config)
        btn_layout.addWidget(self.transform_config_btn)
        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

        self.transformed_config_text = QTextEdit()
        layout.addWidget(self.transformed_config_text)

        self.tabs.addTab(self.transformed_config_frame, "Transformed Config")

    def init_source_schema_tab(self):
        self.source_schema_frame = QWidget()
        layout = QVBoxLayout(self.source_schema_frame)

        btn_layout = QHBoxLayout()
        self.load_source_schema_btn = self.create_standard_button("Load Source Schema",
                                                                  lambda: self.load_schema("source"))
        self.view_table_btn = self.create_standard_button("View Table", self.load_from_table)
        self.save_source_schema_btn = self.create_standard_button("Save Schema to JSON",
                                                                  lambda: self.save_schema_to_json("source"))
        btn_layout.addWidget(self.load_source_schema_btn)
        btn_layout.addWidget(self.view_table_btn)
        btn_layout.addWidget(self.save_source_schema_btn)
        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

        self.source_schema_tree = QTreeWidget()
        self.source_schema_tree.setHeaderLabels(["Name", "Type", "Details"])
        self.source_schema_tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.source_schema_tree)

        self.tabs.addTab(self.source_schema_frame, "Source Schema")

    def init_dest_schema_tab(self):
        self.dest_schema_frame = QWidget()
        layout = QVBoxLayout(self.dest_schema_frame)

        btn_layout = QHBoxLayout()
        self.load_dest_schema_btn = self.create_standard_button("Load Destination Schema",
                                                                lambda: self.load_schema("destination"))
        self.view_table_btn_dest = self.create_standard_button("View Table", self.load_from_table)
        self.save_dest_schema_btn = self.create_standard_button("Save Schema to JSON",
                                                                lambda: self.save_schema_to_json("destination"))
        btn_layout.addWidget(self.load_dest_schema_btn)
        btn_layout.addWidget(self.view_table_btn_dest)
        btn_layout.addWidget(self.save_dest_schema_btn)
        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

        self.dest_schema_tree = QTreeWidget()
        self.dest_schema_tree.setHeaderLabels(["Name", "Type", "Details"])
        self.dest_schema_tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.dest_schema_tree)

        self.tabs.addTab(self.dest_schema_frame, "Destination Schema")

    def init_table_preview_tab(self):
        self.table_preview_frame = QWidget()
        layout = QVBoxLayout(self.table_preview_frame)

        btn_layout = QHBoxLayout()
        self.table_name_label = QLabel("Table Name:")
        btn_layout.addWidget(self.table_name_label)
        btn_layout.addStretch(1)

        self.load_table_data_btn = self.create_standard_button("Load Table Data", self.load_table_data_from_name)
        self.save_table_data_btn = self.create_standard_button("Save Table to JSON", self.save_table_data_to_json)
        btn_layout.addWidget(self.load_table_data_btn)
        btn_layout.addWidget(self.save_table_data_btn)
        layout.addLayout(btn_layout)

        data_group = QGroupBox("Data Preview (First 10 rows)")
        data_layout = QVBoxLayout(data_group)

        self.data_tree = QTreeWidget()
        self.data_tree.setHeaderLabels([])
        data_layout.addWidget(self.data_tree)

        layout.addWidget(data_group)

        self.tabs.addTab(self.table_preview_frame, "Table")

    def init_log_tab(self):
        self.log_frame = QWidget()
        layout = QVBoxLayout(self.log_frame)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        self.tabs.addTab(self.log_frame, "Logs")

    def init_execution_tab(self):
        self.execution_frame = QWidget()
        layout = QVBoxLayout(self.execution_frame)

        btn_layout = QHBoxLayout()
        self.run_transfer_btn = self.create_standard_button("Run Transfer", self.run_transfer)
        self.stop_transfer_btn = self.create_standard_button("Stop", self.stop_transfer)
        btn_layout.addWidget(self.run_transfer_btn)
        btn_layout.addWidget(self.stop_transfer_btn)
        # Прогресс бар
        self.progress = QProgressBar()
        btn_layout.addWidget(self.progress)
        layout.addLayout(btn_layout)

        info_group = QGroupBox("Transfer Information")
        info_layout = QHBoxLayout(info_group)
        self.insert_count_label = QLabel("Records to Insert: 0")
        self.update_count_label = QLabel("Records to Update: 0")
        self.delete_count_label = QLabel("Records to Delete: 0")
        info_layout.addWidget(self.insert_count_label)
        info_layout.addWidget(self.update_count_label)
        info_layout.addWidget(self.delete_count_label)
        layout.addWidget(info_group)

        result_group = QGroupBox("Results")
        result_layout = QVBoxLayout(result_group)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        result_layout.addWidget(self.result_text)
        layout.addWidget(result_group)

        self.tabs.addTab(self.execution_frame, "Execution")

    def load_default_config_at_startup(self):
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_config_path = os.path.join(script_dir, 'default.json')
        try:
            if self.logic.load_config_from_file(default_config_path):
                self.config_text.setPlainText(json.dumps(self.logic.get_config(), indent=2))
        except FileNotFoundError:
            self.logic.create_default_config()
            self.config_text.setPlainText(json.dumps(self.logic.get_config(), indent=2))
        except json.JSONDecodeError:
            self.logic.create_default_config()
            self.config_text.setPlainText(json.dumps(self.logic.get_config(), indent=2))
        except Exception:
            self.logic.create_default_config()
            self.config_text.setPlainText(json.dumps(self.logic.get_config(), indent=2))

    def load_config(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Configuration File", "",
                                                   "JSON files (*.json);;All files (*)")
        if file_path:
            if self.logic.load_config_from_file(file_path):
                self.config_text.setPlainText(json.dumps(self.logic.get_config(), indent=2))

    def save_config(self):
        try:
            config_content = self.config_text.toPlainText()
            config = json.loads(config_content)
            self.logic.set_config(config)
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Configuration File", "",
                                                       "JSON files (*.json);;All files (*)")
            if file_path:
                self.logic.save_config_to_file(file_path)
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", "Invalid JSON in configuration editor")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")

    def new_config(self):
        default_config = self.logic.create_default_config()
        self.config_text.setPlainText(json.dumps(default_config, indent=2))

    def load_schema(self, schema_type):
        self.logic.load_schema(schema_type)

    def save_schema_to_json(self, schema_type):
        """Вызывает метод логики для сохранения схемы в JSON."""
        # Сначала получаем путь к файлу через QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(self, f"Save {schema_type} Schema to JSON", "", "JSON files (*.json);;All files (*)")
        if file_path:
            # Вызываем метод логики, передав ему тип схемы и путь к файлу
            self.logic.save_schema_to_json(schema_type, file_path)


    def display_schema(self, schema, schema_type):
        tree_widget = self.source_schema_tree if schema_type == "source" else self.dest_schema_tree
        tree_widget.clear()
        for table_name, columns in schema.items():
            table_item = QTreeWidgetItem(tree_widget, [table_name, "Table", f"{len(columns)} columns"])
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
                col_item = QTreeWidgetItem(table_item, [col_name, "Column", f"{col_type} {extra_str}".strip()])
                if col_info.get("primary_key"):
                    font = self.font()
                    font.setBold(True)
                    col_item.setFont(0, font)
                    col_item.setFont(1, font)
                    col_item.setFont(2, font)

    def load_from_table(self):
        # Определяем активную вкладку и соответствующее дерево
        current_widget = self.tabs.currentWidget()
        if current_widget == self.source_schema_frame:
            tree = self.source_schema_tree
            schema_type = "source"
        elif current_widget == self.dest_schema_frame:
            tree = self.dest_schema_tree
            schema_type = "destination"
        else:
            QMessageBox.warning(self, "Warning", "Please select a table from the Source or Destination Schema tab")
            return

        selected_items = tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select a table from the schema tree")
            return

        item = selected_items[0]
        # Проверяем, является ли элемент таблицей
        parent_item = item.parent()
        if parent_item:  # Это колонка
            table_name = parent_item.text(0)
        else:  # Это таблица
            table_name = item.text(0)

        self.selected_table[schema_type] = table_name
        self.table_name_label.setText(f"Table: {table_name} from {schema_type}")
        self.tabs.setCurrentWidget(self.table_preview_frame)
        self.logic.load_data(table_name, schema_type)

    def display_data(self, rows, columns):
        self.data_tree.clear()
        if not columns:
            self.data_tree.setHeaderLabels([])
            return

        self.data_tree.setHeaderLabels(columns)
        for row in rows:
            item = QTreeWidgetItem(self.data_tree, [str(row.get(col, "")) for col in columns])
        self.data_tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)

    def load_table_data_from_name(self):
        # Получаем имя таблицы из label
        text = self.table_name_label.text()
        if not text.startswith("Table: "):
            QMessageBox.warning(self, "Warning", "Please select a table first (e.g., via 'View Table' button).")
            return
        # Простой парсер строки "Table: table_name from schema_type"
        try:
            parts = text.split()
            table_name = parts[1]
            schema_type = parts[3]
            self.logic.load_data(table_name, schema_type)
        except IndexError:
            QMessageBox.warning(self, "Warning", "Could not parse table name and schema type from label.")
            return

    def save_table_data_to_json(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Table Data to JSON", "",
                                                   "JSON files (*.json);;All files (*)")
        if file_path:
            # Получаем данные из self.data_tree
            # Это немного сложнее, так как QTreeWidget не хранит исходные данные напрямую
            # Предположим, что данные уже были загружены и отображены
            # Нужно будет отслеживать rows и columns от последнего вызова display_data
            # Для простоты, предположим, что у нас есть атрибуты для хранения последних данных
            # В реальности, это лучше хранить в логике или в отдельном атрибуте GUI
            # Здесь я использую атрибут GUI для демонстрации
            # В идеале, логика должна хранить последние загруженные данные
            # и GUI должен запрашивать их у логики
            # Псевдокод: rows, columns = self.logic.get_last_loaded_data()
            # Пока используем атрибут GUI
            if hasattr(self, '_last_loaded_rows') and hasattr(self, '_last_loaded_columns'):
                self.logic.save_data_to_json(self._last_loaded_rows, self._last_loaded_columns, file_path)
            else:
                QMessageBox.warning(self, "Warning", "No table data loaded to save.")

    def set_last_loaded_data(self, rows, columns):
        """Сохраняет последние загруженные данные для возможного сохранения."""
        self._last_loaded_rows = rows
        self._last_loaded_columns = columns

    def transform_config(self):
        transformed_config = self.logic.transform_config()
        if transformed_config:
            self.transformed_config_text.setPlainText(json.dumps(transformed_config, indent=2))

    def run_transfer(self):
        # Получаем актуальный конфиг из текстового поля GUI
        try:
            config_text = self.config_text.toPlainText()
            config = json.loads(config_text)
            # Передаём конфиг напрямую в logic (обновляем его состояние)
            self.logic.set_config(config)
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", "Invalid JSON in Configuration tab")
            return

        # Теперь вызываем run_transfer, который вернёт обновлённый config
        config = self.logic.run_transfer()
        if config:
            from transfer_worker import TransferWorker
            self.transfer_worker = TransferWorker(config)
            self.transfer_worker.finished_signal.connect(self.on_transfer_finished)
            self.transfer_worker.progress_signal.connect(self.progress.setValue)
            self.transfer_worker.start()

    def stop_transfer(self):
        # Остановка в данном случае означит завершение потока
        # QThread.stop() не рекомендуется и может быть небезопасным
        # Лучше использовать флаг остановки в JobManager
        # Пока просто сбросим прогресс
        self.logic.log_message_signal.emit("Transfer stopped by user (not implemented in JobManager)")
        if hasattr(self, 'transfer_worker') and self.transfer_worker.isRunning():
            self.transfer_worker.terminate()  # Это не рекомендуется, но для демонстрации
            self.transfer_worker.wait()
        self.progress.setValue(0)

    def on_transfer_finished(self, inserted, updated, deleted, status):
        self.insert_count_label.setText(f"Records to Insert: {inserted}")
        self.update_count_label.setText(f"Records to Update: {updated}")
        self.delete_count_label.setText(f"Records to Delete: {deleted}")

        if status == "completed":
            self.result_text.setPlainText(
                f"Transfer completed successfully:\n- {inserted} records inserted\n- {updated} records updated\n- {deleted} records deleted\n")
        else:  # failed
            self.result_text.setPlainText(f"Transfer failed: {status}")

    def append_log(self, message):
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(message)
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()
