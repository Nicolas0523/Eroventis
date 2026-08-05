import React, { useMemo } from "react";

export default function RiskCard({ analysis }) {
  if (!analysis) return null;

  // Динамический и научно честный подсчет среднего риска по всему полигону
  const riskScore = useMemo(() => {
    // Если бэкенд вернул валидный общий счет, используем его
    if (analysis.risk_score && analysis.risk_score > 0) {
      return analysis.risk_score;
    }
    // Иначе высчитываем среднее значение из всех ячеек сетки
    if (analysis.grid && analysis.grid.length > 0) {
      const total = analysis.grid.reduce((sum, cell) => {
        const cellRisk = cell.risk_percent !== undefined ? cell.risk_percent : (cell.risk || 0);
        return sum + cellRisk;
      }, 0);
      return total / analysis.grid.length;
    }
    return 0;
  }, [analysis]);

  const riskPercent = Number(riskScore).toFixed(1);

  const getRiskStatus = (score) => {
    if (score > 60.0) return { text: "High Risk", className: "risk-high", color: "#ef4444" };
    if (score >= 30.0) return { text: "Medium Risk", className: "risk-medium", color: "#f59e0b" };
    return { text: "Low Risk", className: "risk-low", color: "#10b981" };
  };

  const status = getRiskStatus(riskScore);

  return (
    <div className="risk-card glass-panel" style={{ marginBottom: "20px", padding: "16px", background: "rgba(15, 23, 42, 0.8)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.1)" }}>
      <div className="risk-header" style={{ marginBottom: "12px" }}>
        <span 
          className="risk-title" 
          style={{ 
            fontSize: "11px", 
            fontWeight: "600", 
            color: "#94a3b8", 
            letterSpacing: "1px" 
          }}
        >
          OVERALL RISK ASSESSMENT
        </span>
      </div>
      
      <div 
        className="risk-value-container" 
        style={{ 
          display: "flex", 
          justifyContent: "space-between", 
          alignItems: "baseline" 
        }}
      >
        <span 
          className={`risk-level ${status.className}`}
          style={{ 
            fontSize: "18px", 
            fontWeight: "700", 
            color: status.color
          }}
        >
          {status.text}
        </span>
        <span className="risk-percentage" style={{ fontSize: "24px", fontWeight: "800", color: "#ffffff" }}>
          {riskPercent}%
        </span>
      </div>

      <div 
        className="grid-cells-info" 
        style={{ 
          marginTop: "14px", 
          paddingTop: "10px", 
          borderTop: "1px solid rgba(255, 255, 255, 0.05)",
          fontSize: "10.5px", 
          color: "#64748b", 
          letterSpacing: "0.3px",
          fontWeight: "400"
        }}
      >
        Analyzed Area: {analysis.grid?.length || 0} units (10x10 km resolution)
      </div>
    </div>
  );
}