#!/usr/bin/env python
"""
Тестовый запуск DataTransferTool.
Запускает фиксированный набор конфигов из папки configs/.
Количество раундов: 2.
Логи сохраняются в папку results/.
Конфигурация подключения — из внешнего private_settings.py (безопасность).
"""

import sys
import os
import json
import logging
import subprocess
from pathlib import Path
import re

ROUNDS = 1
# --- НАСТРОЙКА ПОЛЬЗОВАТЕЛЯ: укажи нужные конфиги ---
CONFIG_NAMES = [
    "mysql_to_mysql",
    "mysql_to_sqlite",
    "mysql_to_acs",
    "mysql_to_xlsx",
]
# ----------------------------------------------------

# Настройка путей
TEST_DIR = Path(__file__).parent
CONFIGS_DIR = TEST_DIR / "configs"
RESULTS_DIR = TEST_DIR / "results"
TEMP_CONFIGS_DIR = RESULTS_DIR / "temp_configs"

# Создаем папки
RESULTS_DIR.mkdir(exist_ok=True)

# Настройка логирования (для самого скрипта тестирования)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(RESULTS_DIR / "run_tests.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Путь к основному скрипту
MAIN_SCRIPT = TEST_DIR.parent / "main.py"


# 🔐 ВНЕШНИЙ ПУТЬ К БЕЗОПАСНОМУ КОНФИГУ (НЕ В ПРОЕКТЕ!)
CONFIG_DIR = r"D:\Py\dev_config"
sys.path.insert(0, CONFIG_DIR)

try:
    import private_settings
except ImportError as e:
    logging.critical(f"❌ Не удалось импортировать private_settings.py из {CONFIG_DIR}: {e}")
    sys.exit(1)


# Функция запуска одного теста
def run_test(config_path: Path):
    # Имя теста — имя файла без расширения
    test_name = config_path.stem
    log_file = RESULTS_DIR / f"{test_name}.log"
    temp_config_path = TEMP_CONFIGS_DIR / f"{test_name}_resolved.json"

    logging.info(f"▶ Запуск теста: {test_name}")

    try:
        # Читаем оригинальный конфиг
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # --- СНАЧАЛА формируем replace_map ---
        if hasattr(private_settings, "CONFIG") and isinstance(private_settings.CONFIG, dict):
            replace_map = private_settings.CONFIG
        else:
            logging.critical("❌ private_settings.py должен содержать словарь CONFIG = { ... }")
            sys.exit(1)

        logging.debug(f"🔧 replace_map = {replace_map}")

        # Рекурсивная функция замены строк в словаре
        def replace_placeholders(obj):
            if isinstance(obj, dict):
                return {k: replace_placeholders(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_placeholders(item) for item in obj]
            elif isinstance(obj, str):
                # Заменяем, если строка полностью совпадает с ключом из replace_map
                return replace_map.get(obj, obj)
            else:
                return obj

        # Применяем замены
        resolved_config = replace_placeholders(config_data)

        # Логируем в файл
        with open(log_file, "w", encoding="utf-8") as log_f:
            log_f.write(f"=== ORIGINAL CONFIG ===\n")
            log_f.write(json.dumps(config_data, indent=2, ensure_ascii=False) + "\n\n")

        # Сохраняем временный конфиг
        TEMP_CONFIGS_DIR.mkdir(exist_ok=True)
        with open(temp_config_path, 'w', encoding='utf-8') as f:
            json.dump(resolved_config, f, indent=2, ensure_ascii=False)

        # Запускаем main.py с временным конфигом
        result = subprocess.run(
            [sys.executable, str(MAIN_SCRIPT), str(temp_config_path)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=300  # 5 минут
        )

        # Дописываем вывод в лог
        with open(log_file, "a", encoding="utf-8") as log_f:
            log_f.write(f"=== STDOUT ===\n{result.stdout}\n")
            log_f.write(f"=== STDERR ===\n{result.stderr}\n")

        if result.returncode == 0:
            logging.info(f"✅ Тест '{test_name}' прошёл успешно. Лог: {log_file}")
            return True, temp_config_path
        else:
            logging.error(f"❌ Тест '{test_name}' завершился с ошибкой (код: {result.returncode}). Лог: {log_file}")
            return False, temp_config_path

    except Exception as e:
        logging.error(f"❌ Ошибка при запуске теста '{test_name}': {e}")
        return False, None


def cleanup_temp_configs():
    """Удаляет временные конфиги после выполнения всех тестов"""
    if TEMP_CONFIGS_DIR.exists():
        try:
            for temp_file in TEMP_CONFIGS_DIR.iterdir():
                if temp_file.is_file():
                    temp_file.unlink()
            logging.info(f"🗑️ Временные конфиги удалены: {TEMP_CONFIGS_DIR}")
        except Exception as e:
            logging.warning(f"⚠️ Не удалось удалить временные файлы: {e}")
    else:
        logging.debug(f"📁 Папка {TEMP_CONFIGS_DIR} не существует — удаление пропущено.")


def main():
    # Собираем пути к конфигам
    config_files = []
    for name in CONFIG_NAMES:
        json_path = CONFIGS_DIR / f"{name}.json"
        if not json_path.exists():
            logging.critical(f"❌ Конфиг не найден: {json_path}")
            continue
        config_files.append(json_path)

    total_tests = 0
    passed_tests = 0
    created_temp_files = []  # Сохраняем пути к созданным временным файлам

    try:
        for round_num in range(1, ROUNDS + 1):
            logging.info(f"\n🔄 РАУНД {round_num} НАЧАЛСЯ")
            for config_file in config_files:
                total_tests += 1
                success, temp_path = run_test(config_file)
                if success:
                    passed_tests += 1
                if temp_path:
                    created_temp_files.append(temp_path)

    finally:
        # Гарантированное удаление временных файлов
        cleanup_temp_configs()

    # Итог
    logging.info(f"\n📊 ИТОГО: {passed_tests} / {total_tests} тестов пройдено.")
    if passed_tests == total_tests:
        logging.info("🎉 Все тесты прошли успешно!")
        sys.exit(0)
    else:
        failed = total_tests - passed_tests
        logging.error(f"🔥 {failed} тестов провалено.")
        sys.exit(1)


if __name__ == "__main__":
    main()