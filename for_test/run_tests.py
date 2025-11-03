import subprocess
import json
import os
import sys
import tempfile

import logging
import mysql.connector
import sqlite3
import pyodbc

# настройки подключения к mysql
config_dir = r"D:\Py\dev_config"  #
sys.path.insert(0, config_dir)
try:
    # Импортируем настройки из внешнего файла
    import db_config
except ImportError as e:
    print(f"Ошибка импорта файла конфигурации: {e}")
    print(f"Убедитесь, что файл db_config.py существует в {config_dir}")
    sys.exit(1) # Завершаем выполнение, если конфиг не найден

mysql_host = db_config.mysql_host
mysql_user = db_config.mysql_user
mysql_password = db_config.mysql_password
mysql_db1 = db_config.mysql_db1
mysql_db2 = db_config.mysql_db2

python_executable = r"D:\Py\work\8D DataTransfer py3.12-64bit\.venv\Scripts\python.exe"
main_path = r"D:\Py\work\8D DataTransfer py3.12-64bit\main.py"

sqlite_path = "test_db2.db"
access_path = "D:/Py/work/8D DataTransfer py3.12-64bit/for_test/test_db3.accdb"
xlsx_path = "test_db4.xlsx"


# Переопределяем уровни логов на Дебаг
logging.getLogger('connectors.xlsx_source').setLevel(logging.DEBUG)

# Определяем тестовые конфигурации
test_configs = [
    # 1. MySQL -> MySQL
    {
        "source": {
            "type": "mysql",
            "connection_params": {
                "host": mysql_host,
                "port": 3306,
                "user": mysql_user,
                "password": mysql_password,
                "database": mysql_db1
            }
        },
        "destination": {
            "type": "mysql",
            "connection_params": {
                "host": mysql_host,
                "port": 3306,
                "user": mysql_user,
                "password": mysql_password,
                "database": mysql_db2
            }
        },
        "jobs": [{"source": {
                    "table": "table1",
                    },
                    "destination": {
                        "table": "table2",  #
                    },
                }]
    },
    # 2. MySQL -> SQLite
    {
        "source": {
            "type": "mysql",
            "connection_params": {
                "host": mysql_host,
                "port": 3306,
                "user": mysql_user,
                "password": mysql_password,
                "database": mysql_db1
            }
        },
        "destination": {
            "type": "sql",
            "connection_params": {"path": sqlite_path}
        },
        "jobs": [{"tables": ["table1"]}]
    },
    # 3. MySQL -> MS Access
    {
        "source": {
            "type": "mysql",
            "connection_params": {
                "host": mysql_host,
                "port": 3306,
                "user": mysql_user,
                "password": mysql_password,
                "database": mysql_db1
            }
        },
        "destination": {
            "type": "msaccess",
            "connection_params": {"path": access_path}
        },
        "jobs": [{"tables": ["table1"]}]
    },
    # 4. MySQL -> XLSX
    {
        "source": {
            "type": "mysql",
            "connection_params": {
                "host": mysql_host,
                "port": 3306,
                "user": mysql_user,
                "password": mysql_password,
                "database": mysql_db1
            }
        },
        "destination": {
            "type": "xlsx",
            "connection_params": {"path": xlsx_path, "sheet_name": "table1"}
        },
        "jobs": [{"tables": ["table1"]}]
    }
]


# Тестовые данные
data_from = [
    {
        'id': 1,
        'normal_chars': 'Just normal text with letters and numbers 123',
        'problematic_chars': 'This has "quotes", a backslash \\\\, a newline \\n, and a tab \\t.',
        'numeric_value': 42,
        'float_value': 3.14,
        'date_value': '2025-10-27',
        'datetime_value': '2025-10-27 15:30:00',
        'boolean_value': 1
    },
    {
        'id': 2,
        'normal_chars': 'Another normal string',
        'problematic_chars': "More problematic chars: ''single quotes'', /slashes/, and control characters like \\0 or \\r\\n.",
        'numeric_value': -100,
        'float_value': 99.99,
        'date_value': '2020-01-01',
        'datetime_value': '2020-01-01 00:00:00',
        'boolean_value': 0
    }
]

data_to = [
    {
        'id': 1,
        'normal_chars': 'Updated normal text',
        'problematic_chars': 'Updated problematic chars with new line \\n and tab \\t.',
        'numeric_value': 99,
        'float_value': 5.55,
        'date_value': '2025-10-28',
        'datetime_value': '2025-10-28 16:00:00',
        'boolean_value': 0
    },
    {
        'id': 3,
        'normal_chars': 'New record normal string',
        'problematic_chars': 'New problematic chars.',
        'numeric_value': 200,
        'float_value': 12.34,
        'date_value': '2021-01-01',
        'datetime_value': '2021-01-01 01:00:00',
        'boolean_value': 1
    }
]

def create_mysql_table_and_insert_data(host, user, password, database, table_name, data):
    conn = mysql.connector.connect(host=host, user=user, password=password, database=database)
    cursor = conn.cursor()

    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id INT AUTO_INCREMENT PRIMARY KEY,
        normal_chars VARCHAR(255),
        problematic_chars TEXT,
        numeric_value INT,
        float_value DECIMAL(10, 2),
        date_value DATE,
        datetime_value DATETIME,
        boolean_value BOOLEAN
    );
    """
    cursor.execute(create_sql)

    # Удаляем старые данные
    cursor.execute(f"DELETE FROM {table_name};")
    insert_sql = f"""
    INSERT INTO {table_name} (id, normal_chars, problematic_chars, numeric_value, float_value, date_value, datetime_value, boolean_value)
    VALUES (%(id)s, %(normal_chars)s, %(problematic_chars)s, %(numeric_value)s, %(float_value)s, %(date_value)s, %(datetime_value)s, %(boolean_value)s);
    """
    cursor.executemany(insert_sql, data)
    conn.commit()
    cursor.close()
    conn.close()

def create_sqlite_table_and_insert_data(db_path, table_name, data):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id INTEGER PRIMARY KEY,
        normal_chars TEXT,
        problematic_chars TEXT,
        numeric_value INTEGER,
        float_value REAL,
        date_value TEXT,
        datetime_value TEXT,
        boolean_value INTEGER
    );
    """
    cursor.execute(create_sql)

    # Удаляем старые данные
    cursor.execute(f"DELETE FROM {table_name};")
    insert_sql = f"""
    INSERT INTO {table_name} (id, normal_chars, problematic_chars, numeric_value, float_value, date_value, datetime_value, boolean_value)
    VALUES (:id, :normal_chars, :problematic_chars, :numeric_value, :float_value, :date_value, :datetime_value, :boolean_value);
    """
    cursor.executemany(insert_sql, data)
    conn.commit()
    cursor.close()
    conn.close()

def create_access_table_and_insert_data(access_path, table_name, data):
    # Подключение к .accdb файлу Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=path to mdb/accdb file
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={access_path};"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Удаление таблицы, если существует
    try:
        cursor.execute(f"DROP TABLE {table_name};")
        conn.commit()
    except:
        pass

    create_sql = f"""
    CREATE TABLE {table_name} (
        id INTEGER PRIMARY KEY,
        normal_chars TEXT,
        problematic_chars LONGTEXT,
        numeric_value INTEGER,
        float_value DOUBLE,
        date_value DATE,
        datetime_value DATETIME,
        boolean_value BIT
    );
    """
    cursor.execute(create_sql)

    insert_sql = f"""
    INSERT INTO {table_name} (id, normal_chars, problematic_chars, numeric_value, float_value, date_value, datetime_value, boolean_value)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """
    for row in data:
        cursor.execute(insert_sql, tuple(row.values()))
    conn.commit()
    cursor.close()
    conn.close()

def create_xlsx_table_and_insert_data(xlsx_path, sheet_name, data):
    from openpyxl import Workbook

    wb = Workbook()
    # создать нужный лист:
    ws = wb.create_sheet(title=sheet_name) # Создаем лист с нужным именем
    wb.remove(wb["Sheet"]) # Удаляем лист по умолчанию, созданный при инициализации


    if not data:
        wb.save(xlsx_path)
        return

    # Проверяем, что data - это список
    if not isinstance(data, list):
        raise ValueError("Data must be a list of dictionaries.")

    # Проверяем, что все элементы в data - словари
    if not all(isinstance(row, dict) for row in data):
        raise ValueError("All items in data must be dictionaries.")

    # Получаем имена ключей из первого словаря как заголовки
    headers = list(data[0].keys())
    ws.append(headers)

    # Проходим по каждой строке данных (каждый словарь)
    for row_data in data:
        # Создаем список значений, соответствующий порядку заголовков
        row_values = [row_data.get(header, "") for header in headers]
        ws.append(row_values)

    wb.save(xlsx_path)

def run_main_with_config(config_path):
    result = subprocess.run([python_executable, main_path, config_path], capture_output=True, text=True, encoding='utf-8')
    # Выводим stdout всегда
    if result.stdout:
        print("Output:", result.stdout)
    # Выводим stderr всегда, а не только при ошибке
    if result.stderr:
        print("Stderr (might contain logs):", result.stderr)

    if result.returncode != 0:
        print("Error running main.py:")
        # print(result.stderr) # Убираем, так как stderr уже выведен выше
    else:
        print("main.py executed successfully")
        # print("Output:", result.stdout) # Убираем, так как stdout уже выведен выше

def create_config_file(config, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

def main_test():
    logging.getLogger('connectors').setLevel(logging.DEBUG)

    # Создание и заполнение MySQL баз
    create_mysql_table_and_insert_data(mysql_host, mysql_user, mysql_password, mysql_db1, "table1", data_from)
    create_mysql_table_and_insert_data(mysql_host, mysql_user, mysql_password, mysql_db1, "table2", data_to)
    create_mysql_table_and_insert_data(mysql_host, mysql_user, mysql_password, mysql_db2, "test_data", data_to)

    # Создание и заполнение других баз
    create_xlsx_table_and_insert_data(xlsx_path, "table1", data_to)
    create_sqlite_table_and_insert_data(sqlite_path, "table1", data_to)
    create_access_table_and_insert_data(access_path, "table1", data_to)




    # Повторяем тесты 2 раза
    for i in range(2):
        print(f"\n--- Round {i+1} ---")

        # Выполняем каждый тест из списка конфигураций
        for idx, config_data in enumerate(test_configs):
            print(f"  Running test {idx + 1}...")
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
                create_config_file(config_data, tmp.name)
            run_main_with_config(tmp.name)
            os.unlink(tmp.name)


if __name__ == "__main__":
    main_test()