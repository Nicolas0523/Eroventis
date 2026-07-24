import React from "react";
import { GeoJSON } from "react-leaflet";

export default function GridLayer({ gridData }) {
  if (!gridData) return null;

  const getGridStyle = (feature) => {
    const risk = feature.properties?.risk_score ?? 0;

    let color = "#2ecc71"; // Low
    if (risk > 0.6) {
      color = "#e74c3c"; // High
    } else if (risk > 0.3) {
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
        const risk = (
          (feature.properties?.risk_score ?? 0) * 100
        ).toFixed(1);

        layer.bindPopup(`
          <strong>Wind Erosion Risk</strong><br/>
          ${risk}%
        `);
      }}
    />
  );
}