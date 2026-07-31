import time
import ee
from ee.ee_exception import EEException
from datetime import datetime
from config import ndvi_stats

def gee_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except EEException as e:
            if "Too Many Requests" in str(e) and attempt < max_retries - 1:
                time.sleep((attempt + 1) * 3)
            else:
                raise

def resolve_dates(start_date_str: str, end_date_str: str):
    
    default_start = datetime(2024, 1, 1)
    default_end = datetime(2024, 12, 31)

    if not start_date_str or start_date_str.strip() == "":
        start_date = default_start
    else:
        try:
            start_date = datetime.strptime(start_date_str.strip(), "%Y-%m-%d")
        except ValueError:
            print(f"Предупреждение: Неверный формат start_date '{start_date_str}', ставим дефолт.")
            start_date = default_start

    if not end_date_str or end_date_str.strip() == "":
        end_date = default_end
    else:
        try:
            end_date = datetime.strptime(end_date_str.strip(), "%Y-%m-%d")
        except ValueError:
            print(f"Предупреждение: Неверный формат end_date '{end_date_str}', ставим дефолт.")
            end_date = default_end

    if start_date > end_date:
        start_date, end_date = end_date, start_date


    actual_start = start_date.strftime("%Y-%m-%d")
    actual_end = end_date.strftime("%Y-%m-%d")
    is_forecast = False 

    return actual_start, actual_end, is_forecast

def build_risk_image(raw_data, polygon, month):
    ndvi_mean_val = ndvi_stats['mean'].get(float(month), 0.0)
    risk = raw_data["ndvi"] \
        .subtract(ndvi_mean_val) \
        .multiply(-1) \
        .unitScale(-0.05, 0.15) \
        .clamp(0, 1) \
        .rename("risk") \
        .clip(polygon)
    return risk

def get_tile_and_score(risk_image, polygon, scale=1000):
    map_id = gee_retry(lambda: risk_image.getMapId({
        'min': 0, 'max': 1,
        'palette': ['#1a9850', '#fee08b', '#d73027'],
        'forceRgb': True
    }))
    mean_risk = gee_retry(lambda: risk_image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=polygon,
        scale=scale,
        bestEffort=True
    ).getInfo()["risk"])

    return map_id['tile_fetcher'].url_format, round(float(mean_risk), 4)