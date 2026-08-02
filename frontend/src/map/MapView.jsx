import React, { useMemo } from "react";
import { MapContainer, TileLayer, GeoJSON, FeatureGroup } from "react-leaflet";
import { EditControl } from "react-leaflet-draw";

import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";

const getHighContrastColor = (value) => {
  const t = Math.max(0, Math.min(1, value));
  let r, g, b;

  if (t < 0.25) {
    const localT = t / 0.25;
    r = Math.round(16 + (132 - 16) * localT);
    g = Math.round(185 + (204 - 185) * localT);
    b = Math.round(129 + (22 - 129) * localT);
  } else if (t < 0.5) {
    const localT = (t - 0.25) / 0.25;
    r = Math.round(132 + (234 - 132) * localT);
    g = Math.round(204 + (179 - 204) * localT);
    b = Math.round(22 + (8 - 22) * localT);
  } else if (t < 0.75) {
    const localT = (t - 0.5) / 0.25;
    r = Math.round(234 + (249 - 234) * localT);
    g = Math.round(179 + (115 - 179) * localT);
    b = Math.round(8 + (22 - 8) * localT);
  } else {
    const localT = (t - 0.75) / 0.25;
    r = Math.round(249 + (239 - 249) * localT);
    g = Math.round(115 + (68 - 115) * localT);
    b = Math.round(22 + (68 - 22) * localT);
  }

  return `rgb(${r}, ${g}, ${b})`;
};

export default function MapView({ analysis, setPolygon }) {
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

    const risks = analysis.grid
      .map((cell) => cell.risk)
      .filter((r) => r !== undefined && !isNaN(r));

    const minRisk = risks.length > 0 ? Math.min(...risks) : 0;
    const maxRisk = risks.length > 0 ? Math.max(...risks) : 1;
    const range = maxRisk - minRisk;

    const features = analysis.grid
      .filter((cell) => cell.lat !== undefined && cell.lon !== undefined)
      .map((cell) => {
        // Зафиксированный шаг без деления на Math.cos(rad) и без умножения на 1.05
        const step = cell.step_deg || 0.09;
        const halfStep = step / 2;

        const normalizedRisk =
          range > 0.01 ? (cell.risk - minRisk) / range : cell.risk;

        return {
          type: "Feature",
          properties: {
            color: getHighContrastColor(normalizedRisk),
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
        center={[48.0196, 66.9237]}
        zoom={5}
        style={{ height: "100%", width: "100%" }}
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
              rectangle: false,
              circle: false,
              circlemarker: false,
              polyline: false,
              marker: false,
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
            style={(feature) => ({
              fillColor: feature.properties.color,
              fillOpacity: 0.85,
              stroke: false,
              weight: 0,
            })}
          />
        )}
      </MapContainer>
    </div>
  );
}