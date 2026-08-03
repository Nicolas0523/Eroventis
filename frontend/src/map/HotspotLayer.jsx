import React from "react";

export default function HotspotList({ analysis }) {
  if (!analysis) return null;

  const hotspots = analysis.hotspots || [];
  const hasHotspots = hotspots.length > 0;

  return (
    <div className="hotspots-card glass-panel" style={{ marginTop: "20px", padding: "16px" }}>
      <div className="hotspots-header" style={{ marginBottom: "12px" }}>
        <span 
          className="hotspots-title" 
          style={{ 
            fontSize: "11px", 
            fontWeight: "600", 
            color: "#94a3b8", 
            letterSpacing: "1px" 
          }}
        >
          CRITICAL HOTSPOTS
        </span>
      </div>

      {hasHotspots ? (
        <div className="hotspots-list" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {hotspots.map((spot, idx) => (
            <div 
              key={idx} 
              className="hotspot-item"
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "8px 12px",
                background: "rgba(239, 68, 68, 0.1)",
                borderLeft: "3px solid #ef4444",
                borderRadius: "4px",
                fontSize: "12.5px"
              }}
            >
              <span style={{ color: "#fca5a5", fontWeight: "500" }}>
                Hotspot #{idx + 1}
              </span>
              {/* ИСПРАВЛЕНИЕ: Используем spot.max_risk и НЕ умножаем на 100 */}
              <span style={{ color: "#ffffff", fontWeight: "600" }}>
                Risk: {Number(spot.max_risk || 0).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p 
          className="no-hotspots-text" 
          style={{ 
            fontSize: "11px", 
            color: "#475569", 
            lineHeight: "1.4",
            margin: "4px 0 0 0",
            fontStyle: "italic"
          }}
        >
          No critical wind erosion hotspots detected in this area.
        </p>
      )}
    </div>
  );
}