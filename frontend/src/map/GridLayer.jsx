import React from "react";
import { GeoJSON } from "react-leaflet";

export default function GridLayer({ gridData }) {
  if (!gridData) return null;

  const getGridStyle = (feature) => {
    // Риск уже от 0 до 100
    const risk = feature.properties?.risk_score ?? 0;

    let color = "#2ecc71"; // Low
    if (risk > 60.0) {      // Меняем 0.6 на 60.0
      color = "#e74c3c"; // High
    } else if (risk > 30.0) { // Меняем 0.3 на 30.0
      color = "#f39c12"; // Medium
    }

    return {
      fillColor: color,
      fillOpacity: 0.75,
      stroke: false
    };
  };

  return (
    <GeoJSON
      data={gridData}
      style={getGridStyle}
      onEachFeature={(feature, layer) => {
        // Убираем умножение на 100, так как это уже процент
        const risk = (feature.properties?.risk_score ?? 0).toFixed(1);

        layer.bindPopup(`
          <strong>Wind Erosion Risk</strong><br/>
          ${risk}%
        `);
      }}
    />
  );
}