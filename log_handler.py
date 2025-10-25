# log_handler.py
import logging
from PyQt5.QtCore import QObject, pyqtSignal


class LogHandler(QObject, logging.Handler):
    """
    Класс-обработчик для направления сообщений logging в виджет QTextEdit.
    """
    # Сигнал для отправки сообщений в GUI-поток
    log_signal = pyqtSignal(str)

    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.log_signal.connect(self.append_log)

    def emit(self, record):
        """Вызывается, когда логгер получает сообщение."""
        msg = self.format(record)
        # Отправляем сообщение в GUI-поток через сигнал
        self.log_signal.emit(msg + '\n')

    def append_log(self, msg):
        """Добавляет сообщение в текстовое поле лога."""
        cursor = self.text_widget.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(msg)
        self.text_widget.setTextCursor(cursor)
        self.text_widget.ensureCursorVisible()