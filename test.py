# test.py
from typing import List, Dict, Any
import logging  # Добавляем импорт модуля logging
import sqlite3  # Добавлен импорт sqlite3
import os  # Добавлено для проверки существования файла в load_transform_function

# Настройка логирования для этого модуля
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)  # Создаем логгер для этого файла


def create_test_sqlite_db(db_path: str, table_name: str, columns: List[Dict[str, str]],
                          sample_data: List[Dict[str, Any]] = None):
    """
    Создает тестовую SQLite базу данных и таблицу с заданными столбцами.
    При необходимости заполняет таблицу тестовыми данными.

    :param db_path: Путь к файлу базы данных SQLite.
    :param table_name: Имя таблицы.
    :param columns: Список словарей с описанием столбцов, например:
                    [{"name": "product_id", "type": "INTEGER"},
                     {"name": "model", "type": "TEXT"},
                     {"name": "date_added", "type": "TEXT"}] # Используем TEXT для даты/времени в SQLite
    :param sample_data: (Опционально) Список словарей с тестовыми данными для вставки.
    """
    logger.info(f"Создание тестовой SQLite базы: {db_path}, таблица: {table_name}")

    # Убедимся, что директория для файла существует
    directory = os.path.dirname(db_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
        logger.debug(f"Создана директория: {directory}")

    # Подключаемся к базе данных (создаст файл, если не существует)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Формируем строку определения столбцов
    column_defs = []
    for col in columns:
        name = col.get("name")
        col_type = col.get("type", "TEXT").upper()  # По умолчанию TEXT
        # Простое приведение Python типов к SQLite типам, если нужно
        # if col_type == "INT": col_type = "INTEGER"
        # elif col_type == "STRING": col_type = "TEXT"
        # elif col_type == "DATETIME": col_type = "TEXT" # Или NUMERIC
        # Для простоты, предполагаем, что типы уже в формате SQLite
        column_defs.append(f"`{name}` {col_type}")

    columns_str = ", ".join(column_defs)
    create_table_query = f"CREATE TABLE IF NOT EXISTS `{table_name}` ({columns_str});"

    logger.debug(f"Выполнение SQL: {create_table_query}")
    cursor.execute(create_table_query)

    if sample_data:
        logger.info(f"Вставка {len(sample_data)} тестовых записей в таблицу {table_name}.")
        if sample_data:
            first_row = sample_data[0]
            placeholders = ", ".join(["?"] * len(first_row))
            columns_for_insert = ", ".join([f"`{k}`" for k in first_row.keys()])
            insert_query = f"INSERT OR REPLACE INTO `{table_name}` ({columns_for_insert}) VALUES ({placeholders});"  # OR REPLACE может быть полезен для теста

            for row in sample_data:
                cursor.execute(insert_query, list(row.values()))

    conn.commit()
    conn.close()
    logger.info(f"Тестовая база данных {db_path} создана (или обновлена) успешно.")


# Пример использования метода (вне класса, для демонстрации)
def example_usage():
    columns_schema = [
        {"name": "product_id", "type": "INTEGER"},
        {"name": "model", "type": "TEXT"},
        {"name": "date_added", "type": "TEXT"}  # Используем TEXT для даты/времени
    ]

    # Опционально: тестовые данные
    sample_data = [
        {"product_id": 1, "model": "Model A", "date_added": "2023-10-01 10:00:00"},
        {"product_id": 2, "model": "Model B", "date_added": "2023-10-02 11:30:00"},
        {"product_id": 3, "model": "Model C", "date_added": "2023-10-03 14:15:20"},
    ]

    create_test_sqlite_db("test.db", "oc_product", columns_schema, sample_data)


example_usage()
