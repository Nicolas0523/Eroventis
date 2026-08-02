import React, { useMemo } from "react";
import { MapContainer, TileLayer, GeoJSON, FeatureGroup } from "react-leaflet";
import { EditControl } from "react-leaflet-draw";
import L from "leaflet";

import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";

// ДИНАМИКАЛЫҚ ЖӘНЕ СЕЗІМТАЛ ПАЛИТРА: Төменгі деңгейдегі (0-15%) өзгерістерді керемет көрсетеді
const getDynamicCommercialColor = (value) => {
  // Күшейткіш коэффициент (gamma correction) — төменгі қауіптің өзін текстуралы градиентке айналдырады
  const t = Math.pow(Math.max(0, Math.min(1, value)), 0.6);
  let r, g, b;

  if (t < 0.25) {
    const localT = t / 0.25;
    r = Math.round(16 + (90 - 16) * localT);
    g = Math.round(185 + (210 - 185) * localT);
    b = Math.round(129 + (50 - 129) * localT);
  } else if (t < 0.5) {
    const localT = (t - 0.25) / 0.25;
    r = Math.round(90 + (220 - 90) * localT);
    g = Math.round(210 + (195 - 210) * localT);
    b = Math.round(50 + (15 - 50) * localT);
  } else if (t < 0.75) {
    const localT = (t - 0.5) / 0.25;
    r = Math.round(220 + (245 - 220) * localT);
    g = Math.round(195 + (120 - 195) * localT);
    b = Math.round(15 + (20 - 15) * localT);
  } else {
    const localT = (t - 0.75) / 0.25;
    r = Math.round(245 + (239 - 245) * localT);
    g = Math.round(120 + (68 - 120) * localT);
    b = Math.round(20 + (68 - 20) * localT);
  }

  return `rgb(${r}, ${g}, ${b})`;
};

const canvasRenderer = L.canvas({ padding: 0.5 });

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

    // Жаңа v5 спутниктік таргет ауқымын таза анықтау (сырой risk талдауы)
    const risks = analysis.grid
      .map((cell) => cell.risk)
      .filter((r) => r !== undefined && !isNaN(r));

    const minRisk = risks.length > 0 ? Math.min(...risks) : 0;
    const maxRisk = risks.length > 0 ? Math.max(...risks) : 1;
    const range = maxRisk - minRisk;

    const features = analysis.grid
      .filter((cell) => cell.lat !== undefined && cell.lon !== undefined)
      .map((cell) => {
        const step = (cell.step_deg || 0.09) * 1.05;
        const halfStep = step / 2;

        const rawRisk = cell.risk;
        const normalizedRisk = range > 0.001 ? (rawRisk - minRisk) / range : rawRisk;

        return {
          type: "Feature",
          properties: {
            color: getDynamicCommercialColor(normalizedRisk),
            raw_risk: rawRisk,
            ndvi: cell.ndvi,
            wind: cell.wind,
            temp: cell.temp
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

    return {
      type: "FeatureCollection",
      features,
    };
  }, [analysis]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <MapContainer
        ref={mapRef}
        center={[48.0196, 66.9237]}
        zoom={5}
        style={{ height: "100%", width: "100%", background: "#0b0f19" }}
        zoomControl={true}
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
              rectangle: false, circle: false, circlemarker: false, polyline: false, marker: false,
              polygon: {
                allowIntersection: false,
                drawError: { color: "#ef4444", message: "Lines cannot intersect!" },
                shapeOptions: { color: "#3b82f6", weight: 3, fillOpacity: 0.1 },
              },
            }}
          />
        </FeatureGroup>

        {geoJsonData && (
          <GeoJSON
            key={JSON.stringify(analysis?.start_date || "grid")}
            data={geoJsonData}
            renderer={canvasRenderer}
            style={(feature) => ({
              fillColor: feature.properties.color,
              fillOpacity: 0.52,  
              stroke: false,         
              weight: 0,             
              color: "transparent",  
            })}
            onEachFeature={(feature, layer) => {
              // Спутниктік таргетті (0-2.0) процентке айналдырып Popup жасау
              const pctRisk = ((feature.properties.raw_risk / 2.0) * 100).toFixed(1);
              layer.bindPopup(`
                <div style="font-family: sans-serif; font-size: 11px; color: #1e293b;">
                  <strong style="font-size: 12px; color: #0f172a;">Wind Erosion Details</strong><br/>
                  <hr style="margin: 4px 0; border: 0; border-top: 1px solid #e2e8f0;"/>
                  <b>Erosion Risk:</b> ${Math.max(0, pctRisk)}%<br/>
                  <b>NDVI:</b> ${parseFloat(feature.properties.ndvi || 0).toFixed(3)}<br/>
                  <b>Max Wind:</b> ${parseFloat(feature.properties.wind || 0).toFixed(1)} m/s<br/>
                  <b>Temperature:</b> ${parseFloat(feature.properties.temp || 0).toFixed(1)} °C
                </div>
              `);
            }}
          />
        )}
      </MapContainer>
    </div>
  );
}
