import axios from "axios";

const API_BASE_URL = "https://eroventis.onrender.com";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, 
  headers: {
    "Content-Type": "application/json",
  },
});

const formatToGeoJSON = (latLngs) => {
  if (!latLngs || latLngs.length === 0) return null;

  const coordinates = latLngs.map((point) => [point[1], point[0]]);

  const firstPoint = coordinates[0];
  const lastPoint = coordinates[coordinates.length - 1];
  if (firstPoint[0] !== lastPoint[0] || firstPoint[1] !== lastPoint[1]) {
    coordinates.push([firstPoint[0], firstPoint[1]]);
  }

  return {
    geometry: {
      type: "Polygon",
      coordinates: [coordinates], 
    },
  };
};

const getTodayFormatted = () => new Date().toISOString().split("T")[0];

export const pollTaskStatus = async (jobId) => {
  if (!jobId || jobId === "undefined") {
    throw new Error("Invalid Job ID for polling");
  }

  const pollInterval = 4000; 
  const timeout = 180000; 
  const start = Date.now();

  while (Date.now() - start < timeout) {
    try {
      const response = await apiClient.get(`/analyze/status/${jobId}`);
      const task = response.data;

      if (task.status === "done") {
        return task; 
      }

      if (task.status === "error") {
        throw new Error(task.error || "Analysis failed on server.");
      }
    } catch (err) {
      if (err.message && !err.message.includes("timeout")) {
         if (err.response?.data?.error) {
            throw new Error(err.response.data.error);
         }
      }
      
    }

    await new Promise((resolve) => setTimeout(resolve, pollInterval));
  }

  throw new Error("Analysis timed out. Please try again.");
};

export const api = {
  analyze: async (polygon, startDate, endDate) => {
    const geoJson = formatToGeoJSON(polygon);
    const payload = {
      ...geoJson,
      start_date: startDate || getTodayFormatted(),
      end_date: endDate || getTodayFormatted(),
    };
    
    const response = await apiClient.post("/analyze", payload);
    return await pollTaskStatus(response.data.job_id);
  },

  forecastShort: async (polygon, startDate, endDate) => {
    const geoJson = formatToGeoJSON(polygon);
    const today = getTodayFormatted();
    
    const payload = {
      ...geoJson,
      start_date: startDate || today, 
      end_date: endDate || today,
    };
    
    const response = await apiClient.post("/analyze/short", payload);
    return await pollTaskStatus(response.data.job_id);
  },

  analyzeClimate: async (polygon, startDate, endDate) => {
    const geoJson = formatToGeoJSON(polygon);
    const today = getTodayFormatted();

    const payload = {
      ...geoJson,
      start_date: startDate || today, 
      end_date: endDate || today,
    };
    
    const response = await apiClient.post("/analyze/climate", payload);
    return await pollTaskStatus(response.data.job_id);
  },

  getStatus: async (jobId) => {
    const response = await apiClient.get(`/analyze/status/${jobId}`);
    return response.data;
  },

  askAssistant: async (question, analysisData = null) => {
    const payload = {
      message: question,
      analysis_data: analysisData
        ? {
            risk_score: analysisData.risk_score,
            total_cells: analysisData.grid?.length || 0,
            worst_cells: [...(analysisData.grid || [])]
              .filter((cell) => cell.risk !== undefined && !isNaN(cell.risk))
              .sort((a, b) => b.risk - a.risk)
              .slice(0, 5),
            hotspots_count: analysisData.hotspots?.length || 0,
          }
        : null, 
    };

    const response = await apiClient.post("/api/chat", payload);
    return response.data; 
  },
};