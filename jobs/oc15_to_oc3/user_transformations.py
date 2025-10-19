def transform_upd_data(upd_data, formatted_source, formatted_destination):
    print("это функция transform_upd_data")
    return upd_data
from datetime import datetime
from typing import List, Dict, Any

def transform_ins_data(ins_data, formatted_source, formatted_destination):
    print("это функция transform_ins_data")
    return ins_data
def transform_del_data(del_data, formatted_source, formatted_destination):
    print("это функция transform_del_data")
    return del_data

def transform_source(formatted_source: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    updated_records = []
    for record in formatted_source:
        # Создаём копию записи, чтобы не изменять оригинальные данные
        new_record = record.copy()

        # Копируем date_added в date_modified
        new_record['date_modified'] = new_record.get('date_added')

        # Устанавливаем фиксированные значения
        new_record['language_id'] = 1
        new_record['currency_id'] = 1
        new_record['currency_code'] = 'RUB'

        updated_records.append(new_record)

    return updated_records

def transform_destination(formatted_destination):
    print("это функция transform_destination")
    return formatted_destination