import { useState } from "react";

export function ControlPanel({ onRunAnalysis, loading, polygon }) {
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [analysisType, setAnalysisType] = useState("historical"); 

  const handleTypeChange = (e) => {
    const newType = e.target.value;
    setAnalysisType(newType);

    if (newType === "climate") {
      setStartDate("2040-01-01");
      setEndDate("2050-12-31");
    } else if (newType === "historical") {
      setStartDate("2024-01-01");
      setEndDate("2024-12-31");
    }
  };

  const handleAnalyzeClick = () => {
    onRunAnalysis(polygon, startDate, endDate, analysisType);
  };

  const isClimate = analysisType === "climate";

  return (
    <div className="control-panel glass-panel">
      <h3 className="panel-title">Wind Erosion Analysis</h3>
      
      {/* Выбор типа анализа */}
      <div className="input-group">
        <label>Analysis Type</label>
        <select 
          className="custom-input" 
          value={analysisType} 
          onChange={handleTypeChange}
        >
          <option value="historical">Historical Analysis</option>
          <option value="short">10-Day Forecast</option>
          <option value="climate">Climate Scenario (2040-2050)</option>
        </select>
      </div>

      {analysisType !== "short" && (
        <>
          <div className="input-group">
            <label>Start Date</label>
            <input 
              type="date" 
              className="custom-input" 
              value={startDate} 
              disabled={isClimate}
              style={{
                opacity: isClimate ? 0.6 : 1,
                cursor: isClimate ? "not-allowed" : "pointer"
              }}
              onChange={(e) => setStartDate(e.target.value)} 
            />
          </div>
          <div className="input-group">
            <label>End Date</label>
            <input 
              type="date" 
              className="custom-input" 
              value={endDate} 
              disabled={isClimate}
              style={{
                opacity: isClimate ? 0.6 : 1,
                cursor: isClimate ? "not-allowed" : "pointer"
              }}
              onChange={(e) => setEndDate(e.target.value)} 
            />
          </div>

          {isClimate && (
            <p style={{ fontSize: "10px", color: "#94a3b8", marginTop: "2px", lineHeight: "1.3" }}>
              ℹ️ Fixed timeframe: CMIP6 / IPCC 2040–2050 climate projections horizon.
            </p>
          )}
        </>
      )}

      <button
        className="btn-analyze"
        disabled={loading || !polygon} 
        onClick={handleAnalyzeClick}
        style={{ marginTop: isClimate ? "12px" : "16px" }}
      >
        {loading ? "Analyzing..." : "Run AI Analysis"}
      </button>

      {!polygon && (
        <p style={{ fontSize: '9.5px', color: '#64748b', marginTop: '6px', textAlign: 'center' }}>
          * Draw a polygon on the map to unlock analysis
        </p>
      )}
    </div>
  );
}