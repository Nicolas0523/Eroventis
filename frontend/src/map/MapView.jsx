import React, { useMemo, useEffect } from "react";
import { MapContainer, TileLayer, GeoJSON, FeatureGroup, useMap } from "react-leaflet";
import { EditControl } from "react-leaflet-draw";
import L from "leaflet";
import "leaflet.heat"; // Подключаем библиотеку тепловой карты

import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";

// --- НОВЫЙ КОМПОНЕНТ ПЛАВНОЙ ТЕПЛОВОЙ КАРТЫ ---
function TrueHeatmapLayer({ grid }) {
  const map = useMap();

  useEffect(() => {
    if (!grid || grid.length === 0) return;

    // 1. Собираем точки для тепловой карты: [широта, долгота, интенсивность]
    const heatPoints = grid
      .filter((cell) => cell.lat !== undefined && cell.lon !== undefined)
      .map((cell) => {
        const risk = cell.risk_percent !== undefined ? cell.risk_percent : (cell.risk || 0);
        // Нормализуем риск от 0.0 до 1.0
        const intensity = Math.max(0, Math.min(1, risk / 100));
        return [cell.lat, cell.lon, intensity];
      });

    // 2. Создаем слой тепловой карты с красивым градиентом
    const heatLayer = L.heatLayer(heatPoints, {
      radius: 35, // Размер пятна от одной ячейки (можно менять)
      blur: 40,   // Сила размытия (создает тот самый плавный переход)
      maxZoom: 10,
      max: 1.0,   // Максимальное значение интенсивности
      gradient: {
        0.15: '#10b981', // Зеленый (низкий риск)
        0.40: '#84cc16', // Салатовый
        0.60: '#eab308', // Желтый (повышенный)
        0.80: '#f97316', // Оранжевый (высокий)
        1.00: '#ef4444'  // Красный (критический)
      }
    });

    heatLayer.addTo(map);

    // Очистка при размонтировании или обновлении данных
    return () => {
      map.removeLayer(heatLayer);
    };
  }, [map, grid]);

  return null;
}

export default function MapView({ analysis, setPolygon, mapRef }) {
  const _onCreate = (e) => {
    const { layerType, layer } = e;
    if (layerType === "polygon") {
      const latlngs = layer.getLatLngs()[0];
      const formattedCoords = latlngs.map((ln) => [ln.lat, ln.lng]);
      setPolygon(formattedCoords);
    }
  };

  const _onDeleted = () => {
    setPolygon(null);
  };

  const geoJsonData = useMemo(() => {
    if (!analysis || !analysis.grid || analysis.grid.length === 0) return null;

    const rawGrid = analysis.grid.filter(
      (cell) => cell.lat !== undefined && cell.lon !== undefined
    );

    const features = rawGrid.map((cell) => {
      const step = cell.step_deg || 0.09;
      const halfStep = step / 2;

      let tempC = parseFloat(cell.temp ?? cell.raw_temp ?? 0);
      if (tempC > 100) {
        tempC = tempC - 273.15;
      }

      const riskPercent = cell.risk_percent !== undefined ? cell.risk_percent : (cell.risk || 0);

      return {
        type: "Feature",
        properties: {
          risk: riskPercent,
          ndvi: cell.ndvi ?? cell.raw_ndvi ?? 0,
          wind: cell.wind ?? cell.raw_wind ?? 0,
          temp: tempC,
          soil_moisture: cell.soil_moisture ?? 0.2,
          slope: cell.slope ?? 1.0,
          soil_type: cell.soil_type ?? 2.0,
        },
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [cell.lon - halfStep, cell.lat - halfStep],
              [cell.lon + halfStep, cell.lat - halfStep],
              [cell.lon + halfStep, cell.lat + halfStep],
              [cell.lon - halfStep, cell.lat + halfStep],
              [cell.lon - halfStep, cell.lat - halfStep],
            ],
          ],
        },
      };
    });

    return { type: "FeatureCollection", features };
  }, [analysis]);

  const layerKey = useMemo(() => {
    if (!analysis || !analysis.grid) return "empty_layer";
    return `grid_layer_${analysis.grid.length}_${Date.now()}`;
  }, [analysis]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <MapContainer
        ref={mapRef}
        center={[48.0196, 66.9237]}
        zoom={5}
        style={{ height: "100%", width: "100%", background: "#060810" }}
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        {/* Добавляем наш новый плавный тепловой слой */}
        {analysis?.grid && <TrueHeatmapLayer grid={analysis.grid} />}

        <FeatureGroup>
          <EditControl
            position="topleft"
            onCreated={_onCreate}
            onDeleted={_onDeleted}
            draw={{
              rectangle: false,
              circle: false,
              circlemarker: false,
              polyline: false,
              marker: false,
              polygon: {
                allowIntersection: false,
                drawError: {
                  color: "#ef4444",
                  message: "Lines cannot intersect!",
                },
                shapeOptions: {
                  color: "#3b82f6",
                  weight: 2,
                  fillOpacity: 0.15,
                },
              },
            }}
          />
        </FeatureGroup>

        {/* Невидимая сетка GeoJSON для сохранения работы Попапов при клике! */}
        {geoJsonData && (
          <GeoJSON
            key={layerKey}
            data={geoJsonData}
            style={() => ({
              fillOpacity: 0, // Делаем квадраты невидимыми
              stroke: false,  // Убираем границы
              weight: 0,
            })}
            onEachFeature={(feature, layer) => {
              layer.bindPopup(`
                <div style="font-family: system-ui, -apple-system, sans-serif; font-size: 12px; line-height: 1.6; color: #f8fafc; background: #0f172a; padding: 4px; border-radius: 8px; min-width: 180px;">
                  <div style="font-size: 13px; font-weight: 600; color: #38bdf8; margin-bottom: 4px; border-bottom: 1px solid #334155; padding-bottom: 4px;">
                    🌍 Wind Erosion Details
                  </div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #94a3b8;">Risk:</span> 
                    <span style="color: ${feature.properties.risk > 70 ? '#ef4444' : feature.properties.risk > 30 ? '#f59e0b' : '#10b981'}; font-weight: bold;">
                      ${parseFloat(feature.properties.risk || 0).toFixed(1)}%
                    </span>
                  </div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #94a3b8;">NDVI:</span> 
                    <span>${parseFloat(feature.properties.ndvi || 0).toFixed(3)}</span>
                  </div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #94a3b8;">Max Wind:</span> 
                    <span>${parseFloat(feature.properties.wind || 0).toFixed(1)} m/s</span>
                  </div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #94a3b8;">Temperature:</span> 
                    <span>${parseFloat(feature.properties.temp || 0).toFixed(1)} °C</span>
                  </div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #94a3b8;">Soil Moisture:</span> 
                    <span>${parseFloat(feature.properties.soil_moisture || 0).toFixed(3)}</span>
                  </div>
                  <div style="display: flex; justify-content: space-between;">
                    <span style="color: #94a3b8;">Soil Type:</span> 
                    <span>${feature.properties.soil_type || 'N/A'}</span>
                  </div>
                </div>
              `);
            }}
          />
        )}
      </MapContainer>
    </div>
  );
}