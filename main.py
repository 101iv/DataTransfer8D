# main.py
import sys
import os
import json
import logging

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication
from logic import DataTransferLogic, run_cli_transfer
from gui import DataTransferGUI
from log_handler import LogHandler

# todo проверить сравнение для xlsx access

def main():
    # Проверяем аргументы командной строки
    if len(sys.argv) > 2:
        print("Usage: python main.py [config_file_path]", file=sys.stderr)
        sys.exit(1)

    config_path_from_args = None
    if len(sys.argv) == 2:
        config_path_from_args = sys.argv[1]
        if not os.path.isfile(config_path_from_args):
            print(f"Error: Configuration file not found: {config_path_from_args}", file=sys.stderr)
            sys.exit(1)

    if config_path_from_args:
        # Режим выполнения CLI
        sys.exit(run_cli_transfer(config_path_from_args))
    else:
        # Режим выполнения GUI
        app = QApplication(sys.argv)

        # иконка
        icon_path = os.path.join(os.path.dirname(__file__), 'app_icon.png')  # Укажите имя вашего файла
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Warning: Icon file not found at {icon_path}", file=sys.stderr)

        # Настройка логирования
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Создание логики
        logic = DataTransferLogic()

        # Создание GUI
        gui = DataTransferGUI(logic)

        # Настройка обработчика логов для GUI
        text_handler = LogHandler(gui.log_text)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        text_handler.setFormatter(formatter)

        # Добавление обработчика к корневому логгеру
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(text_handler)

        # Также можно добавить обработчик в консоль
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # Подключение сигналов логики к слотам GUI
        logic.log_message_signal.connect(gui.append_log)
        logic.schema_loaded_signal.connect(gui.display_schema)
        logic.data_loaded_signal.connect(lambda rows, cols: [gui.display_data(rows, cols), gui.set_last_loaded_data(rows, cols)])
        logic.transfer_finished_signal.connect(gui.on_transfer_finished)
        logic.progress_update_signal.connect(gui.progress.setValue)

        gui.show()
        sys.exit(app.exec_())


if __name__ == "__main__":
    main()