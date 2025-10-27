# connectors/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List

# Базовый класс для источника данных
class DataSource(ABC):
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def fetch_data(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def insert_data(self, data: List[Dict[str, Any]], table_name: str):
        pass

    @abstractmethod
    def update_data(self, updates: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        pass

    @abstractmethod
    def delete_data(self, deletions: List[Dict[str, Any]], key_fields: List[str], table_name: str):
        pass

    @abstractmethod
    def standard_formatting(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pass