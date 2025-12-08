@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo    Установщик виртуального окружения
echo ========================================
echo.

:init
set "VENV_DIR=.venv"
set "REQ_FILE=requirements.txt"
set "MIN_VERSION=3.8"

:check_python
echo [ШАГ 1] Проверка Python ^>=%MIN_VERSION% 32-bit...
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python не найден в PATH!
    echo.
    echo Установите Python ^>=%MIN_VERSION% 32-bit:
    echo https://www.python.org/downloads/
    echo.
    echo ✅ Обязательно отметьте "Add Python to PATH"
    pause
    exit /b 1
)

:: Проверяем минимальную версию - БЕЗ ВРЕМЕННОГО ФАЙЛА
for /f "tokens=1-2 delims=. " %%a in ('python -c "import sys; print(sys.version_info.major, sys.version_info.minor)"') do (
    set "MAJOR=%%a"
    set "MINOR=%%b"
)

for /f %%i in ('python -c "import sys; print('32bit' if sys.maxsize ^<^= 2**32 else '64bit')"') do set "PYTHON_ARCH=%%i"

echo Версия Python: !MAJOR!.!MINOR!
echo Архитектура: !PYTHON_ARCH!

:: Проверка минимальной версии
for /f "tokens=1,2 delims=." %%a in ("%MIN_VERSION%") do (
    set "MIN_MAJOR=%%a"
    set "MIN_MINOR=%%b"
)

if !MAJOR! lss !MIN_MAJOR! (
    echo ❌ Версия Python слишком старая. Требуется ^>= %MIN_VERSION%
    pause
    exit /b 1
)

if !MAJOR! equ !MIN_MAJOR! if !MINOR! lss !MIN_MINOR! (
    echo ❌ Версия Python слишком старая. Требуется ^>= %MIN_VERSION%
    pause
    exit /b 1
)

if not "!PYTHON_ARCH!"=="32bit" (
    echo ❌ Требуется 32-bit версия Python
    echo Найдена: !PYTHON_ARCH! версия
    echo.
    echo Установите Python 32-bit версию
    pause
    exit /b 1
)

echo ✅ Python !MAJOR!.!MINOR! 32-bit подходит
echo.

:create_venv
echo [ШАГ 2] Создание виртуального окружения...
echo.

if exist "%VENV_DIR%" (
    echo Виртуальное окружение уже существует.
    set /p RECREATE="Пересоздать? (y/N): "
    if /i "!RECREATE!"=="y" (
        echo Удаление старого окружения...
        rmdir /s /q "%VENV_DIR%" 2>nul
        goto create_new_venv
    ) else (
        echo Использую существующее окружение.
        goto activate_and_install
    )
)

:create_new_venv
echo Создание виртуального окружения...
python -m venv "%VENV_DIR%"

if %errorlevel% neq 0 (
    echo ❌ Ошибка создания виртуального окружения
    echo Попробуйте: python -m ensurepip --default-pip
    pause
    exit /b 1
)

echo ✅ Виртуальное окружение создано
echo.

:activate_and_install
echo [ШАГ 3] Установка зависимостей...
echo.

set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"

if not exist "%VENV_PYTHON%" (
    echo ❌ Не найден Python в виртуальном окружении
    pause
    exit /b 1
)

if not exist "%REQ_FILE%" (
    echo ⚠️  Файл зависимостей "%REQ_FILE%" не найден
    echo    Будет создан пустой файл
    echo # Зависимости проекта > "%REQ_FILE%"
)

echo Установка зависимостей из %REQ_FILE%...
"%VENV_PIP%" install --upgrade pip
"%VENV_PIP%" install -r "%REQ_FILE%"

if %errorlevel% neq 0 (
    echo ⚠️  Ошибка установки зависимостей
    echo Попытка установить основные пакеты...
    "%VENV_PIP%" install setuptools wheel
)

echo ✅ Зависимости установлены
echo.

:final
echo ========================================
echo            УСТАНОВКА ЗАВЕРШЕНА
echo ========================================
echo.
echo Что сделано:
echo 1. ✓ Проверен Python ^>=%MIN_VERSION% 32-bit
echo 2. ✓ Создано виртуальное окружение в %VENV_DIR%
echo 3. ✓ Установлены зависимости из %REQ_FILE%
echo.
echo Использование:
echo 1. Активировать окружение: %VENV_DIR%\Scripts\activate
echo 2. Деактивировать: deactivate
echo.
echo ========================================
pause
exit /b 0