import React from "react";

function convertToCommercialPercentage(score) {
  if (score === undefined || score === null || isNaN(score)) return 0;
  
  let percentage = score > 2.0 ? score : (score / 2.0) * 100.0;
  return Math.min(Math.max(percentage, 0), 100.0);
}

export default function HotspotList({ analysis }) {
  if (!analysis) return null;

  let hotspots = analysis.hotspots || [];

  if (hotspots.length === 0 && analysis.grid && analysis.grid.length > 0) {
    hotspots = [...analysis.grid]
      .filter(cell => cell.risk !== undefined && !isNaN(cell.risk))
      .sort((a, b) => b.risk - a.risk)
      .slice(0, 5)
      .map((cell) => ({
        lat: cell.lat,
        lon: cell.lon,
        risk: cell.risk,
        max_risk: cell.risk 
      }));
  }

  if (hotspots.length === 0) {
    return (
      <div className="hotspots-card glass-panel" style={{ marginTop: "16px", padding: "12px", width: "100%" }}>
        <span style={{ fontSize: "10px", fontWeight: "600", color: "#94a3b8" }}>CRITICAL HOTSPOTS</span>
        <div style={{ color: "#ef4444", fontSize: "11.5px", marginTop: "8px" }}>No high-risk zones detected.</div>
      </div>
    );
  }

  return (
    <div 
      className="hotspots-card glass-panel" 
      style={{ 
        marginTop: "16px", 
        padding: "12px",
        width: "100%",
        boxSizing: "border-box"
      }}
    >
      <div className="hotspots-header" style={{ marginBottom: "8px" }}>
        <span 
          className="hotspots-title" 
          style={{ 
            fontSize: "10px", 
            fontWeight: "600", 
            color: "#94a3b8", 
            letterSpacing: "1px" 
          }}
        >
          CRITICAL HOTSPOTS
        </span>
      </div>

      <div className="hotspots-list" style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        {hotspots.map((spot, idx) => {
          const rawRisk = 
            spot.max_risk !== undefined ? spot.max_risk :
            spot.risk !== undefined ? spot.risk :
            spot.avg_risk !== undefined ? spot.avg_risk : 
            0;

          const parsedRisk = parseFloat(rawRisk);
          const finalPercentage = convertToCommercialPercentage(parsedRisk);

          return (
            <div 
              key={idx} 
              className="hotspot-item"
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "6px 10px",
                background: "rgba(239, 68, 68, 0.1)",
                borderLeft: "3px solid #ef4444",
                borderRadius: "4px",
                fontSize: "11.5px"
              }}
            >
              <span style={{ color: "#fca5a5", fontWeight: "500" }}>
                Hotspot #{idx + 1}
              </span>
              <span style={{ color: "#ffffff", fontWeight: "600" }}>
                Risk: {finalPercentage.toFixed(1)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}