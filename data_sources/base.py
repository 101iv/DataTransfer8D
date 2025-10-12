# data_sources/base.py
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