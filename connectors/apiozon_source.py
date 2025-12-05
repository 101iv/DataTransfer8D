# connectors/ozon_source.py
from .base import DataSource
from typing import Any, Dict, List
import requests
import logging
import time

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OzonDataSource(DataSource):
    def __init__(self, connection_params: Dict[str, Any]):
        """
        connection_params должен содержать:
            - client_id: str
            - api_key: str
            - base_url: str (опционально, по умолчанию: https://api-seller.ozon.ru)
        """
        self.client_id = connection_params.get("client_id")
        self.api_key = connection_params.get("api_key")
        self.base_url = connection_params.get("base_url", "https://api-seller.ozon.ru")
        self.headers = {
            "Client-Id": self.client_id,
            "Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def connect(self):
        """Проверка подключения — простой запрос к любому безопасному эндпоинту (например, /v1/warehouse/list)"""
        try:
            logger.info("Проверка подключения к Ozon API...")
            response = self.session.post(
                f"{self.base_url}/v1/warehouse/list",
                json={"page": 1, "page_size": 1}
            )
            if response.status_code == 200:
                logger.info("Подключение к Ozon API успешно.")
            else:
                error_msg = f"Ozon API connection failed: {response.status_code} {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Ошибка подключения к Ozon: {e}")
            raise

    def fetch_data(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Основной метод для получения данных.
        query — это путь к API-эндпоинту (например, '/v1/report/products/create').
        params — параметры для тела POST-запроса.
        """
        if not params:
            params = {}

        endpoint = query.strip()
        table_name = self._normalize_table_name(endpoint)

        logger.info(f"Запрос к Ozon API: {endpoint}, таблица: {table_name}")

        try:
            # Жёстко определяем схему и логику обработки для каждого эндпоинта
            if endpoint == "/v1/report/products/create":
                return self._fetch_v1_report_products_create(params)
            else:
                raise Exception(f"Неизвестный эндпоинт: {endpoint}")
        except Exception as e:
            logger.error(f"Ошибка при получении данных из Ozon API: {e}")
            raise

    def _normalize_table_name(self, endpoint: str) -> str:
        """Преобразует путь API в имя таблицы, заменяя спецсимволы на подчёркивания."""
        return endpoint.strip("/").replace("/", "_").replace("-", "_")

    def _fetch_v1_report_products_create(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Обработка эндпоинта: /v1/report/products/create
        Создаёт отчёт и ожидает его готовности.
        """
        logger.debug("Выполняем запрос к /v1/report/products/create")

        # Шаг 1: Создаём отчёт
        create_url = f"{self.base_url}/v1/report/products/create"
        creation_payload = {
            "filter": params.get("filter", {}),
            "language": params.get("language", "DEFAULT"),
            "report_type": params.get("report_type", "ALL")
        }

        logger.debug(f"Отправка запроса на создание отчёта: {creation_payload}")
        response = self.session.post(create_url, json=creation_payload)

        if response.status_code != 200:
            error_msg = f"Ошибка создания отчёта: {response.status_code} {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)

        data = response.json()
        report_id = data.get("result", {}).get("task_id")
        if not report_id:
            raise Exception("Не получен task_id из ответа на создание отчёта")

        logger.info(f"Отчёт инициализирован. task_id: {report_id}. Ожидаем готовности...")

        # Шаг 2: Ожидаем готовности отчёта
        status_url = f"{self.base_url}/v1/report/info"
        for _ in range(20):  # Максимум 20 попыток
            time.sleep(5)  # Ждём 5 сек между попытками
            status_response = self.session.post(status_url, json={"task_id": report_id})
            if status_response.status_code != 200:
                continue

            status_data = status_response.json()
            state = status_data.get("result", {}).get("state")
            if state == "SUCCESS":
                file_url = status_data["result"]["file"]
                logger.info(f"Отчёт готов: {file_url}")
                # Шаг 3: Скачиваем данные
                file_response = requests.get(file_url)
                if file_response.status_code == 200:
                    rows = file_response.json()  # Предполагаем JSON
                    # Применяем стандартное форматирование
                    return self.standard_formatting(rows.get("result", []))
                else:
                    raise Exception(f"Не удалось скачать файл: {file_response.status_code}")
            elif state == "FAILED":
                raise Exception("Отчёт завершился с ошибкой")

        raise Exception("Превышено время ожидания готовности отчёта")

    def get_schema(self) -> Dict[str, Any]:
        """
        Возвращает схему для поддерживаемых таблиц (эндпоинтов).
        Здесь — только для `/v1/report/products/create`.
        """
        return {
            "v1_report_products_create": [
                {"name": "product_id", "type": "BIGINT", "not_null": False, "default": None, "extra": "", "primary_key": False},
                {"name": "name", "type": "VARCHAR", "not_null": False, "default": None, "extra": "", "primary_key": False},
                {"name": "price", "type": "DECIMAL", "not_null": False, "default": None, "extra": "", "primary_key": False},
                {"name": "old_price", "type": "DECIMAL", "not_null": False, "default": None, "extra": "", "primary_key": False},
                {"name": "discount", "type": "INT", "not_null": False, "default": None, "extra": "", "primary_key": False},
                {"name": "sku", "type": "BIGINT", "not_null": False, "default": None, "extra": "", "primary_key": False},
                {"name": "stock", "type": "INT", "not_null": False, "default": None, "extra": "", "primary_key": False},
                {"name": "status", "type": "VARCHAR", "not_null": False, "default": None, "extra": "", "primary_key": False},
                # Другие поля — можно добавить по мере необходимости
            ]
        }

    def build_select_query(self, table_name: str, fields: List[str] = None) -> str:
        """
        Возвращает API-путь по имени таблицы.
        Пример: v1_report_products_create -> /v1/report/products/create
        """
        if table_name == "v1_report_products_create":
            return "/v1/report/products/create"
        else:
            raise Exception(f"Нет соответствия API для таблицы: {table_name}")

    # --- Заглушки для неподдерживаемых операций (только read-only) ---

    def insert_data(self, data: List[Dict[str, Any]], table_name: str):
        logger.warning("OzonDataSource: insert_data не поддерживается (read-only)")
        pass

    def update_data(self, updates: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        logger.warning("OzonDataSource: update_data не поддерживается (read-only)")
        pass

    def delete_data(self, deletions: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        logger.warning("OzonDataSource: delete_data не поддерживается (read-only)")
        pass

    def disconnect(self):
        """Закрытие сессии"""
        self.session.close()
        logger.info("Соединение с Ozon API закрыто.")

    def standard_formatting(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Стандартное форматирование данных.
        Можно расширить под особенности Ozon.
        """
        formatted_data = []
        for row in data:
            formatted_row = {}
            for key, value in row.items():
                if isinstance(value, (dict, list)):
                    formatted_row[key] = str(value)  # Упрощаем сложные типы
                else:
                    formatted_row[key] = value
            formatted_data.append(formatted_row)
        logger.debug(f"Форматирование данных завершено: {len(formatted_data)} строк")
        return formatted_data