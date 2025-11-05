#!/usr/bin/env python
"""
Автоматизированный тестовый запуск DataTransferTool.
Поддерживает параметры: --config, --rounds, --test-num, --no-cleanup.
"""

import sys
import os
import json
import logging
import subprocess
import tempfile
import argparse
from pathlib import Path

# Настройка пути к конфигу
CONFIG_DIR = r"D:\Py\dev_config"
sys.path.insert(0, str(CONFIG_DIR))

try:
    import db_config
except ImportError as e:
    print(f"❌ Ошибка импорта db_config.py: {e}")
    print(f"Убедитесь, что файл существует в: {CONFIG_DIR}")
    sys.exit(1)

# Пути к файлам
TEST_DIR = Path(__file__).parent
DATA_FILE = TEST_DIR / "test_data.json"
CONFIGS_FILE = TEST_DIR / "test_configs.json"
RESULTS_DIR = TEST_DIR / "results"

python_executable = r"D:\Py\work\8D DataTransfer py3.12-64bit\.venv\Scripts\python.exe"
main_path = r"D:\Py\work\8D DataTransfer py3.12-64bit\main.py"

sqlite_path = "test_db2.db"
access_path = "D:/Py/work/8D DataTransfer py3.12-64bit/for_test/test_db3.accdb"
xlsx_path = "test_db4.xlsx"

# Создаем папку для результатов
RESULTS_DIR.mkdir(exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(RESULTS_DIR / "test_runner.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Загрузка тестовых данных
def load_json_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.critical(f"Не удалось загрузить {path}: {e}")
        sys.exit(1)

test_data = load_json_file(DATA_FILE)
data_from = test_data["data_from"]
data_to = test_data["data_to"]

test_configs = load_json_file(CONFIGS_FILE)

# Замена шаблонов в конфигах
def resolve_config_placeholders(config):
    replacements = {
        "MYSQL_HOST": db_config.mysql_host,
        "MYSQL_USER": db_config.mysql_user,
        "MYSQL_PASSWORD": db_config.mysql_password,
        "MYSQL_DB1": db_config.mysql_db1,
        "MYSQL_DB2": db_config.mysql_db2,
    }
    config_str = json.dumps(config)
    for key, value in replacements.items():
        config_str = config_str.replace(f'"{key}"', f'"{value}"')
    return json.loads(config_str)

# Подключение к базам
def create_mysql_table_and_insert_data(host, user, password, database, table_name, data):
    import mysql.connector
    try:
        conn = mysql.connector.connect(host=host, user=user, password=password, database=database)
        cursor = conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
        cursor.execute(f"""
            CREATE TABLE {table_name} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                normal_chars VARCHAR(255),
                problematic_chars TEXT,
                numeric_value INT,
                float_value DECIMAL(10,2),
                date_value DATE,
                datetime_value DATETIME,
                boolean_value BOOLEAN
            );
        """)
        insert_sql = f"""
            INSERT INTO {table_name} (id, normal_chars, problematic_chars, numeric_value, float_value, date_value, datetime_value, boolean_value)
            VALUES (%(id)s, %(normal_chars)s, %(problematic_chars)s, %(numeric_value)s, %(float_value)s, %(date_value)s, %(datetime_value)s, %(boolean_value)s)
        """
        cursor.executemany(insert_sql, data)
        conn.commit()
        cursor.close()
        conn.close()
        logging.debug(f"✅ MySQL: Данные загружены в {database}.{table_name}")
    except Exception as e:
        logging.error(f"❌ Ошибка MySQL: {e}")
        raise

def create_sqlite_table_and_insert_data(db_path, table_name, data):
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
        cursor.execute(f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY,
                normal_chars TEXT,
                problematic_chars TEXT,
                numeric_value INTEGER,
                float_value REAL,
                date_value TEXT,
                datetime_value TEXT,
                boolean_value INTEGER
            );
        """)
        cursor.executemany(f"INSERT INTO {table_name} VALUES (:id, :normal_chars, :problematic_chars, :numeric_value, :float_value, :date_value, :datetime_value, :boolean_value)", data)
        conn.commit()
        conn.close()
        logging.debug(f"✅ SQLite: Данные загружены в {db_path}")
    except Exception as e:
        logging.error(f"❌ Ошибка SQLite: {e}")
        raise

def create_access_table_and_insert_data(access_path, table_name, data):
    import pyodbc
    try:
        conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={access_path};"
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        try:
            cursor.execute(f"DROP TABLE {table_name};")
        except:
            pass
        cursor.execute(f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY,
                normal_chars TEXT,
                problematic_chars MEMO,
                numeric_value INTEGER,
                float_value DOUBLE,
                date_value DATE,
                datetime_value DATETIME,
                boolean_value BIT
            );
        """)
        for row in data:
            cursor.execute(f"""
                INSERT INTO {table_name} (id, normal_chars, problematic_chars, numeric_value, float_value, date_value, datetime_value, boolean_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, list(row.values()))
        conn.commit()
        conn.close()
        logging.debug(f"✅ Access: Данные загружены в {access_path}")
    except Exception as e:
        logging.error(f"❌ Ошибка Access: {e}")
        raise

def create_xlsx_table_and_insert_data(xlsx_path, sheet_name, data):
    from openpyxl import Workbook
    try:
        wb = Workbook()
        ws = wb.create_sheet(sheet_name)
        wb.remove(wb.active)
        if data:
            ws.append(list(data[0].keys()))
            for row in data:
                ws.append([row[key] for key in data[0].keys()])
        wb.save(xlsx_path)
        logging.debug(f"✅ XLSX: Данные загружены в {xlsx_path}")
    except Exception as e:
        logging.error(f"❌ Ошибка XLSX: {e}")
        raise

def run_main_with_config(config_path, test_name):
    python_exec = getattr(db_config, "python_executable", sys.executable)
    main_script = Path(__file__).parent.parent / "main.py"

    log_file = RESULTS_DIR / f"{test_name.replace(' ', '_').lower()}.log"

    with open(log_file, "w", encoding="utf-8") as log_f:
        logging.info(f"▶ Запуск теста: {test_name}")
        result = subprocess.run(
            [python_exec, str(main_script), str(config_path)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=300  # 5 минут
        )
        log_f.write(f"=== STDOUT ===\n{result.stdout}\n")
        log_f.write(f"=== STDERR ===\n{result.stderr}\n")

        if result.returncode == 0:
            logging.info(f"✅ Тест '{test_name}' прошёл успешно.")
            return True
        else:
            logging.error(f"❌ Тест '{test_name}' завершился с ошибкой (code={result.returncode}). Лог: {log_file}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Запуск тестов для DataTransferTool")
    parser.add_argument('--rounds', type=int, default=2, help='Количество повторов всех тестов')
    parser.add_argument('--test-num', type=int, help='Запустить только тест с номером N (1-4)')
    parser.add_argument('--no-cleanup', action='store_true', help='Не удалять временные файлы')
    parser.add_argument('--config', help='Путь к кастомному JSON-конфигу (пропускает стандартные тесты)')
    args = parser.parse_args()

    # Если передан --config, запускаем только его
    if args.config:
        if not Path(args.config).exists():
            logging.error(f"Конфиг не найден: {args.config}")
            sys.exit(1)
        success = run_main_with_config(args.config, "CustomConfig")
        sys.exit(0 if success else 1)

    # Подготовка данных
    logging.info("🔁 Подготовка тестовых данных...")
    create_mysql_table_and_insert_data(db_config.mysql_host, db_config.mysql_user, db_config.mysql_password, db_config.mysql_db1, "table1", data_from)
    create_mysql_table_and_insert_data(db_config.mysql_host, db_config.mysql_user, db_config.mysql_password, db_config.mysql_db1, "table2", data_to)
    create_mysql_table_and_insert_data(db_config.mysql_host, db_config.mysql_user, db_config.mysql_password, db_config.mysql_db2, "test_data", data_to)

    create_sqlite_table_and_insert_data(sqlite_path, "table1", data_to)
    create_xlsx_table_and_insert_data(xlsx_path, "table1", data_to)
    create_access_table_and_insert_data(access_path, "table1", data_to)

    # Запуск тестов
    total_tests = 0
    passed_tests = 0

    for round_num in range(1, args.rounds + 1):
        logging.info(f"\n🔄 РАУНД {round_num} НАЧАЛСЯ")
        for idx, raw_config in enumerate(test_configs):
            if args.test_num and (args.test_num - 1) != idx:
                continue

            config = resolve_config_placeholders(raw_config)
            test_name = config.get("name", f"Test-{idx+1}")
            total_tests += 1

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
                json.dump(config, tmp, indent=2)
                tmp.flush()
                success = run_main_with_config(tmp.name, test_name)
                if success:
                    passed_tests += 1

    # Итог
    logging.info(f"\n📊 Результаты: {passed_tests}/{total_tests} тестов пройдено.")
    if passed_tests == total_tests:
        logging.info("🎉 Все тесты пройдены успешно!")
        sys.exit(0)
    else:
        logging.error("🔥 Некоторые тесты провалились.")
        sys.exit(1)

if __name__ == "__main__":
    main()