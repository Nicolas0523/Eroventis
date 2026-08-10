import ee
from datetime import datetime, timedelta


def load_raw_data(polygon, start_date, end_date):

    fallback_flags = {"ndvi": False, "era5": False}

    def get_ndvi(start, end):
        collection = ee.ImageCollection("MODIS/061/MOD13A2") \
            .filterBounds(polygon) \
            .filterDate(start, end)

        size = collection.size().getInfo()

        if size == 0:
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            end_dt   = datetime.strptime(end,   "%Y-%m-%d")
            start    = start_dt.replace(year=start_dt.year - 1).strftime("%Y-%m-%d")
            end      = end_dt.replace(year=end_dt.year - 1).strftime("%Y-%m-%d")
            print(f"MODIS: no data, falling back to {start} → {end}")
            collection = ee.ImageCollection("MODIS/061/MOD13A2") \
                .filterBounds(polygon) \
                .filterDate(start, end)
            fallback_flags["ndvi"] = True  

        return collection \
            .mean() \
            .select("NDVI") \
            .multiply(0.0001) \
            .rename("NDVI_now") \
            .clip(polygon)

    ndvi = get_ndvi(start_date, end_date)

    def get_era5(start, end):
        collection = ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY") \
            .filterBounds(polygon) \
            .filterDate(start, end)

        size = collection.size().getInfo()

        if size == 0:
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            end_dt   = datetime.strptime(end,   "%Y-%m-%d")
            start    = start_dt.replace(year=start_dt.year - 1).strftime("%Y-%m-%d")
            end      = end_dt.replace(year=end_dt.year - 1).strftime("%Y-%m-%d")
            print(f"ERA5: no data, falling back to {start} → {end}")
            collection = ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY") \
                .filterBounds(polygon) \
                .filterDate(start, end)
            fallback_flags["era5"] = True 

        return collection

    era5_hourly = get_era5(start_date, end_date)
    era5_mean   = era5_hourly.mean()

    wind_mean = era5_mean.expression(
        'sqrt(u*u + v*v)', {
            'u': era5_mean.select('u_component_of_wind_10m'),
            'v': era5_mean.select('v_component_of_wind_10m')
        }).rename('wind_mean').clip(polygon)

    wind_max = era5_hourly.map(lambda img: img.expression(
        'sqrt(u*u + v*v)', {
            'u': img.select('u_component_of_wind_10m'),
            'v': img.select('v_component_of_wind_10m')
        })
    ).max().rename('wind_max').clip(polygon)

    rain = era5_hourly.select('total_precipitation') \
        .mean().rename('rain').clip(polygon)

    tempC = era5_hourly.select('temperature_2m') \
        .mean().subtract(273.15).rename('tempC').clip(polygon)

    soil_moisture = era5_hourly.select('volumetric_soil_water_layer_1') \
        .mean().rename('soil_moisture').clip(polygon)

    evaporation = era5_hourly.select('potential_evaporation_hourly') \
        .mean().rename('evaporation').clip(polygon)

    slope = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003")) \
        .rename('slope').clip(polygon)

    soil_type = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02") \
        .select('b0').rename('soil_type').clip(polygon)

    biome = ee.Image("ESA/WorldCover/v200/2021") \
        .select('Map').rename('biome').clip(polygon)

    return {
        "ndvi":          ndvi,
        "wind_mean":     wind_mean,
        "wind_max":      wind_max,
        "rain":          rain,
        "tempC":         tempC,
        "soil_moisture": soil_moisture,
        "evaporation":   evaporation,
        "slope":         slope,
        "soil_type":     soil_type,
        "biome":         biome,
        "used_fallback": fallback_flags["ndvi"] or fallback_flags["era5"], 
    }


def load_raw_data_multi_year(polygon, start_date, end_date):
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt   = datetime.strptime(end_date,   "%Y-%m-%d")

    if (end_dt - start_dt).days <= 365:
        return load_raw_data(polygon, start_date, end_date)

    yearly_results = []

    for year in range(start_dt.year, end_dt.year + 1):
        start = f"{year}-01-01"
        end   = f"{year}-12-31"

        yearly_raw_data = load_raw_data(polygon, start, end)
        yearly_results.append(yearly_raw_data)

    #avg data
    ndvi_collection = ee.ImageCollection([r["ndvi"] for r in yearly_results])
    avg_ndvi = ndvi_collection.mean()

    wind_mean_collection = ee.ImageCollection([r['wind_mean'] for r in yearly_results])
    avg_wind_mean = wind_mean_collection.mean()

    wind_max_collection = ee.ImageCollection([r['wind_max'] for r in yearly_results])
    avg_wind_max = wind_max_collection.mean()

    rain_collection = ee.ImageCollection([r["rain"] for r in yearly_results])
    avg_rain = rain_collection.mean()

    tempC_collection = ee.ImageCollection([r["tempC"] for r in yearly_results])
    avg_tempC = tempC_collection.mean()

    soil_moisture_collection = ee.ImageCollection([r["soil_moisture"] for r in yearly_results])
    avg_soil_moisture = soil_moisture_collection.mean()

    evaporation_collection = ee.ImageCollection([r["evaporation"] for r in yearly_results])
    avg_evaporation = evaporation_collection.mean()

    any_fallback = any(r.get("used_fallback", False) for r in yearly_results)

    return {
        "ndvi":          avg_ndvi,
        "wind_mean":     avg_wind_mean,
        "wind_max":      avg_wind_max,
        "rain":          avg_rain,
        "tempC":         avg_tempC,
        "soil_moisture": avg_soil_moisture,
        "evaporation":   avg_evaporation,
        "slope":         yearly_results[0]["slope"],
        "soil_type":     yearly_results[0]["soil_type"],
        "biome":         yearly_results[0]["biome"],
        "used_fallback": any_fallback,
    }