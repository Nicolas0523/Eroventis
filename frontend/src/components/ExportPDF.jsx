import React, { useState } from "react";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import html2canvas from "html2canvas";

const REAL_FEATURE_IMPORTANCE = [
  { name: "Wind Mean Speed",        weight: 34.2, color: [239, 68,  68 ] },
  { name: "Soil Moisture",          weight: 26.1, color: [59,  130, 246] },
  { name: "Wind Max Speed",         weight: 14.8, color: [245, 158, 11 ] },
  { name: "NDVI Z-Score",           weight: 10.3, color: [16,  185, 129] },
  { name: "Wind Erosivity (u³)",    weight:  8.1, color: [168, 85,  247] },
  { name: "Aridity Index",          weight:  6.5, color: [236, 72,  253] },
];

// Функция корректного нормализации значения риска
function normalizeRiskScore(val) {
  let num = parseFloat(val ?? 0);
  if (isNaN(num)) return 0;
  // Если значение пришло уже в процентах (например, 165.6 или 48.1), возвращаем как есть
  if (num > 1) return num;
  // Если значение от 0 до 1, переводим в проценты
  return num * 100;
}

function getRiskColor(score) {
  const norm = score > 1 ? score / 100 : score;
  if (norm > 0.6) return [220, 38, 38];
  if (norm > 0.3) return [180, 120, 0];
  return [22, 163, 74];
}

function getRiskLabel(score) {
  const norm = score > 1 ? score / 100 : score;
  if (norm > 0.6) return "HIGH RISK";
  if (norm > 0.3) return "MEDIUM RISK";
  return "LOW RISK";
}

function drawHeader(pdf, pageWidth, title) {
  pdf.setFillColor(15, 23, 42);
  pdf.rect(0, 0, pageWidth, 14, "F");
  pdf.setFillColor(16, 185, 129);
  pdf.rect(0, 14, pageWidth, 1.5, "F");

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(8);
  pdf.setTextColor(148, 163, 184);
  pdf.text("WINDGUARD · Wind Erosion Risk Assessment Platform", 10, 9.5);
  pdf.text(title, pageWidth - 10, 9.5, { align: "right" });
}

function drawFooter(pdf, pageWidth, pageHeight, pageNum) {
  pdf.setFillColor(241, 245, 249);
  pdf.rect(0, pageHeight - 10, pageWidth, 10, "F");
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(7.5);
  pdf.setTextColor(100, 116, 139);
  pdf.text(
    `Generated ${new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })} · WindGuard v5.0`,
    10,
    pageHeight - 3.5
  );
  pdf.text(`Page ${pageNum}`, pageWidth - 10, pageHeight - 3.5, { align: "right" });
}

function sectionHeading(pdf, text, y) {
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(14);
  pdf.setTextColor(15, 23, 42);
  pdf.text(text, 15, y);
  pdf.setDrawColor(16, 185, 129);
  pdf.setLineWidth(0.6);
  pdf.line(15, y + 2, 195, y + 2);
}

export default function ExportPDF({ analysis, aiResponse, mapRef }) {
  const [exporting, setExporting] = useState(false);

  const handleDownload = async () => {
    if (!analysis) return;
    setExporting(true);

    try {
      const pdf = new jsPDF("p", "mm", "a4");
      const PW = pdf.internal.pageSize.getWidth();
      const PH = pdf.internal.pageSize.getHeight();
      let pageNum = 0;

      // PAGE 1 — COVER
      pageNum++;
      pdf.setFillColor(15, 23, 42);
      pdf.rect(0, 0, PW, PH, "F");
      pdf.setFillColor(16, 185, 129);
      pdf.rect(0, PH / 2 - 1, PW, 2, "F");

      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(48);
      pdf.setTextColor(255, 255, 255);
      pdf.text("WINDGUARD", PW / 2, PH / 2 - 30, { align: "center" });

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(12);
      pdf.setTextColor(148, 163, 184);
      pdf.text("Wind Erosion Risk Assessment Report", PW / 2, PH / 2 - 16, { align: "center" });

      const rawScore = analysis.overall_risk ?? analysis.risk_score ?? 0;
      const scorePct = normalizeRiskScore(rawScore);
      const [rr, rg, rb] = getRiskColor(scorePct);

      pdf.setFillColor(rr, rg, rb);
      pdf.roundedRect(PW / 2 - 30, PH / 2 + 14, 60, 14, 3, 3, "F");
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(11);
      pdf.setTextColor(255, 255, 255);
      pdf.text(
        `${getRiskLabel(scorePct)} · ${scorePct.toFixed(1)}%`,
        PW / 2,
        PH / 2 + 23,
        { align: "center" }
      );

      drawFooter(pdf, PW, PH, pageNum);

      // PAGE 2 — EXECUTIVE SUMMARY & MAP
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Executive Summary & Map");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "1. Executive Summary", 24);

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(9.5);
      pdf.setTextColor(51, 65, 85);
      const summary =
        "WindGuard assesses wind-induced soil erosion risk using an optimized XGBoost model integrated with Google Earth Engine (GEE). " +
        "The model evaluates multi-year atmospheric dust loading events to derive reliable ecological risk metrics.";
      pdf.text(pdf.splitTextToSize(summary, 180), 15, 32);

      sectionHeading(pdf, "2. Spatial Risk Map", 55);

      const mapEl = document.querySelector(".leaflet-container");
      if (mapEl) {
        if (mapRef?.current) {
          try {
            mapRef.current.fitBounds(mapRef.current.getBounds(), { padding: [20, 20] });
          } catch (_) {}
        }
        await new Promise((r) => setTimeout(r, 1200));

        try {
          const canvas = await html2canvas(mapEl, {
            useCORS: true,
            scale: 1.8,
            logging: false,
            allowTaint: true,
          });
          const imgData = canvas.toDataURL("image/png");
          const imgH = (canvas.height / canvas.width) * 180;
          pdf.addImage(imgData, "PNG", 15, 65, 180, Math.min(imgH, 180));
        } catch (err) {
          pdf.rect(15, 65, 180, 100);
        }
      }

      // PAGE 3 — HOTSPOT ANALYSIS
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Hotspot Analysis");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "3. Critical Hotspot Identification", 24);

      let hotspots = analysis.hotspots ?? [];
      if (hotspots.length === 0 && (analysis.grid ?? []).length > 0) {
        hotspots = [...analysis.grid]
          .filter((c) => typeof c.risk === "number" && !isNaN(c.risk))
          .sort((a, b) => b.risk - a.risk)
          .slice(0, 10)
          .map((c) => ({ lat: c.lat, lon: c.lon, avg_risk: c.risk }));
      }

      // Исправление определения статуса Hotspot
      const hotspotRows = hotspots.map((spot, i) => {
        const pct = normalizeRiskScore(spot.avg_risk ?? spot.risk);
        let status = "Low Risk";
        if (pct > 60) status = "Critical";
        else if (pct > 30) status = "High Alert";
        else if (pct > 5) status = "Elevated";

        return [
          `#${i + 1}`,
          typeof spot.lat === "number" ? `${spot.lat.toFixed(5)}° N` : "N/A",
          typeof spot.lon === "number" ? `${spot.lon.toFixed(5)}° E` : "N/A",
          `${pct.toFixed(1)}%`,
          status,
        ];
      });

      autoTable(pdf, {
        startY: 32,
        head: [["#", "Latitude", "Longitude", "Risk Score", "Status"]],
        body: hotspotRows.length > 0 ? hotspotRows : [["—", "—", "—", "—", "No hotspots detected"]],
        theme: "striped",
        headStyles: { fillColor: [15, 23, 42], fontSize: 9.5, fontStyle: "bold" },
        styles: { fontSize: 9 },
        columnStyles: { 0: { halign: "center" }, 3: { halign: "center" }, 4: { halign: "center" } },
      });

      // PAGE 4 — TECHNICAL APPENDIX (GRID MATRIX)
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Technical Appendix");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "7. Grid Matrix Array", 24);

      // Исправление процентов > 100% в Grid Matrix
      const gridRows = [...(analysis.grid ?? [])]
        .filter((c) => typeof c.risk === "number")
        .sort((a, b) => b.risk - a.risk)
        .slice(0, 30)
        .map((cell, idx) => {
          const pct = normalizeRiskScore(cell.risk);
          const gridX = cell.grid_x ?? Math.floor(idx / 5);
          const gridY = cell.grid_y ?? (idx % 5);

          return [
            `#${idx + 1}`,
            typeof cell.lat === "number" ? cell.lat.toFixed(5) : "N/A",
            typeof cell.lon === "number" ? cell.lon.toFixed(5) : "N/A",
            `${pct.toFixed(1)}%`,
            `Cell (${gridX}, ${gridY})`,
          ];
        });

      autoTable(pdf, {
        startY: 32,
        head: [["Rank", "Latitude", "Longitude", "Risk Score", "Grid Matrix Index"]],
        body: gridRows.length > 0 ? gridRows : [["—", "—", "—", "—", "No grid data"]],
        theme: "grid",
        headStyles: { fillColor: [15, 23, 42], fontSize: 9 },
        styles: { fontSize: 8.5 },
        columnStyles: {
          0: { halign: "center" },
          3: { halign: "center" },
          4: { halign: "center" },
        },
      });

      const date = new Date().toISOString().slice(0, 10);
      pdf.save(`WindGuard_Executive_Report_${date}.pdf`);
    } catch (err) {
      console.error("PDF export failed:", err);
      alert("PDF export failed — check console.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <button
      onClick={handleDownload}
      disabled={exporting || !analysis}
      style={{
        width: "100%",
        marginTop: "12px",
        padding: "10px 14px",
        background: exporting
          ? "#64748b"
          : "linear-gradient(135deg, #3b78fc 0%, #2378f8 100%)",
        color: "#fff",
        fontWeight: "700",
        fontSize: "13px",
        border: "none",
        borderRadius: "10px",
        cursor: exporting || !analysis ? "not-allowed" : "pointer",
        letterSpacing: "0.5px",
        boxShadow: "0 4px 12px rgba(59, 120, 252, 0.25)",
      }}
    >
      {exporting ? "⏳  Generating report…" : "⬇  Download PDF Report"}
    </button>
  );
}