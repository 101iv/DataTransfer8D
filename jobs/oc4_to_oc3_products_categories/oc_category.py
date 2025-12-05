from typing import List, Dict, Any

def transform_source(formatted_source: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    updated_records = []
    for record in formatted_source:
        # Создаём копию записи, чтобы не изменять оригинальные данные
        new_record = record.copy()

        # Копируем date_added в date_modified
        new_record['column'] = 0
        new_record['top'] = 1
        updated_records.append(new_record)

    return updated_records