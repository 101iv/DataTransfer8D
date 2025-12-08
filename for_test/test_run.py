import sys
import platform


def check_environment():
    # Проверяем, запускается ли из виртуального окружения
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✓ Запущено в виртуальном окружении")
        print(f"Путь интерпретатора: {sys.executable}")
        print(f"Путь к окружению: {sys.prefix}")
    else:
        print("✗ НЕ в виртуальном окружении!")
        print("Завершаю выполнение...")
        sys.exit(1)

    # Проверяем пути импорта
    print("\nПути импорта Python (полный список):")
    for i, path in enumerate(sys.path):
        print(f"  [{i:2}] {path}")


if __name__ == "__main__":
    check_environment()
    print(f"Версия Python: {sys.version}")
    print(f"Архитектура: {platform.architecture()[0]}")
    print(f"Путь к интерпретатору: {sys.executable}")
    print(f"Platform: {platform.platform()}")