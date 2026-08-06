import React, { useMemo } from "react";
import { MapContainer, TileLayer, GeoJSON, FeatureGroup } from "react-leaflet";
import { EditControl } from "react-leaflet-draw";
import L from "leaflet";

import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";

// Плавная палитра для научной тепловой карты
const getDynamicCommercialColor = (value) => {
  const t = Math.max(0, Math.min(1, value));
  let r, g, b;

  if (t < 0.25) {
    const localT = t / 0.25;
    r = Math.round(16 + (90 - 16) * localT);
    g = Math.round(185 + (210 - 185) * localT);
    b = Math.round(129 + (50 - 129) * localT);
  } else if (t < 0.5) {
    const localT = (t - 0.25) / 0.25;
    r = Math.round(90 + (245 - 90) * localT);
    g = Math.round(210 + (210 - 210) * localT);
    b = Math.round(50 + (30 - 50) * localT);
  } else if (t < 0.75) {
    const localT = (t - 0.5) / 0.25;
    r = Math.round(245 + (249 - 245) * localT);
    g = Math.round(210 + (115 - 210) * localT);
    b = Math.round(30 + (22 - 30) * localT);
  } else {
    const localT = (t - 0.75) / 0.25;
    r = Math.round(249 + (220 - 249) * localT);
    g = Math.round(115 + (38 - 115) * localT);
    b = Math.round(22 + (38 - 22) * localT);
  }

  return `rgb(${r}, ${g}, ${b})`;
};

const svgRenderer = L.svg();

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
      const halfStep = (step / 2);

      const riskPercent = cell.risk_percent !== undefined ? cell.risk_percent : (cell.risk || 0);
      const normalizedRisk = Math.max(0, Math.min(1, riskPercent / 100));

      let tempC = parseFloat(cell.temp ?? cell.raw_temp ?? 0);
      if (tempC > 100) {
        tempC = tempC - 273.15;
      }

      return {
        type: "Feature",
        properties: {
          color: getDynamicCommercialColor(normalizedRisk),
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
      {/* Полностью убираем белые рамки, тени и крестик у попапов Leaflet */}
      <style>{`
        .leaflet-popup-content-wrapper, 
        .leaflet-popup-tip {
          background: #0f172a !important;
          color: #f8fafc !important;
          box-shadow: none !important;
          border: none !important;
        }
        .leaflet-popup-content-wrapper {
          padding: 0 !important;
          border-radius: 8px !important;
          overflow: hidden !important;
        }
        .leaflet-popup-content {
          margin: 0 !important;
          line-height: normal !important;
        }
        .leaflet-container a.leaflet-popup-close-button {
          display: none !important;
        }
      `}</style>

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

        {geoJsonData && (
          <GeoJSON
            key={layerKey}
            data={geoJsonData}
            renderer={svgRenderer}
            style={(feature) => ({
              fillColor: feature.properties.color,
              fillOpacity: 0.9, 
              stroke: false, 
              color: feature.properties.color, 
              opacity: 0.9, 
            })}
            onEachFeature={(feature, layer) => {
              const formatNumber = (val, decimals = 1) => 
                typeof val === 'number' ? val.toFixed(decimals) : (val || '0');

              layer.bindPopup(`
                <div style="font-family: system-ui, -apple-system, sans-serif; font-size: 12px; line-height: 1.6; color: #f8fafc; background: #0f172a; padding: 4px; border-radius: 8px; min-width: 180px;">
                  <div style="font-size: 13px; font-weight: 600; color: #38bdf8; margin-bottom: 4px; border-bottom: 1px solid #334155; padding-bottom: 4px;">
                    🌍 Wind Erosion Details
                  </div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #94a3b8;">Risk:</span> 
                    <span style="color: ${feature.properties.risk > 70 ? '#ef4444' : feature.properties.risk > 30 ? '#f59e0b' : '#10b981'}; font-weight: bold;">
                      ${formatNumber(feature.properties.risk, 1)}%
                    </span>
                  </div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #94a3b8;">NDVI:</span> 
                    <span>${formatNumber(feature.properties.ndvi, 3)}</span>
                  </div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #94a3b8;">Max Wind:</span> 
                    <span>${formatNumber(feature.properties.wind, 1)} m/s</span>
                  </div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #94a3b8;">Temperature:</span> 
                    <span>${formatNumber(feature.properties.temp, 1)} °C</span>
                  </div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="color: #94a3b8;">Soil Moisture:</span> 
                    <span>${formatNumber(feature.properties.soil_moisture, 3)}</span>
                  </div>
                  <div style="display: flex; justify-content: space-between;">
                    <span style="color: #94a3b8;">Soil Type:</span> 
                    <span>${formatNumber(feature.properties.soil_type, 1)}</span>
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