import React, { useState } from "react";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import html2canvas from "html2canvas";

// Данные SHAP Feature Importance
const REAL_FEATURE_IMPORTANCE = [
  { name: "Wind Mean Speed",        weight: 34.2, color: [239, 68,  68 ] },
  { name: "Soil Moisture",          weight: 26.1, color: [59,  130, 246] },
  { name: "Wind Max Speed",         weight: 14.8, color: [245, 158, 11 ] },
  { name: "NDVI Z-Score",           weight: 10.3, color: [16,  185, 129] },
  { name: "Wind Erosivity (u³)",    weight:  8.1, color: [168, 85,  247] },
  { name: "Aridity Index",          weight:  6.5, color: [236, 72,  253] },
];

function normalizeRiskScore(val) {
  let num = parseFloat(val ?? 0);
  if (isNaN(num)) return 0;
  if (num > 1) return num;
  return num * 100;
}

function getRiskColor(scorePct) {
  if (scorePct >= 60) return [220, 38, 38];   // High Risk (Red)
  if (scorePct >= 30) return [217, 119, 6];   // Medium Risk (Amber)
  return [22, 163, 74];                       // Low Risk (Green)
}

function getRiskLabel(scorePct) {
  if (scorePct >= 60) return "CRITICAL RISK";
  if (scorePct >= 30) return "HIGH ALERT";
  return "ELEVATED / LOW";
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
    `Generated ${new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })} · WindGuard v5.0 (AI Core)`,
    10,
    pageHeight - 3.5
  );
  pdf.text(`Page ${pageNum}`, pageWidth - 10, pageHeight - 3.5, { align: "right" });
}

function sectionHeading(pdf, text, y) {
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(13);
  pdf.setTextColor(15, 23, 42);
  pdf.text(text, 15, y);
  pdf.setDrawColor(16, 185, 129);
  pdf.setLineWidth(0.6);
  pdf.line(15, y + 2, 195, y + 2);
}

export default function ExportPDF({ analysis, aiResponse, mapRef, userName = "Authorized User" }) {
  const [exporting, setExporting] = useState(false);

  const handleDownload = async () => {
    if (!analysis) return;
    setExporting(true);

    try {
      const pdf = new jsPDF("p", "mm", "a4");
      const PW = pdf.internal.pageSize.getWidth();  // 210
      const PH = pdf.internal.pageSize.getHeight(); // 297
      let pageNum = 0;

      const rawScore = analysis.overall_risk ?? analysis.risk_score ?? 0;
      const scorePct = normalizeRiskScore(rawScore);
      const [rr, rg, rb] = getRiskColor(scorePct);

      // ==================================================================
      // PAGE 1 — COVER
      // ==================================================================
      pageNum++;
      pdf.setFillColor(15, 23, 42);
      pdf.rect(0, 0, PW, PH, "F");

      pdf.setFillColor(16, 185, 129);
      pdf.rect(0, PH / 2 - 20, PW, 2, "F");

      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(42);
      pdf.setTextColor(255, 255, 255);
      pdf.text("WINDGUARD", PW / 2, PH / 2 - 40, { align: "center" });

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(12);
      pdf.setTextColor(148, 163, 184);
      pdf.text("Wind Erosion Risk Assessment Report", PW / 2, PH / 2 - 28, { align: "center" });

      // Color Badge
      pdf.setFillColor(rr, rg, rb);
      pdf.roundedRect(PW / 2 - 40, PH / 2, 80, 16, 4, 4, "F");
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(12);
      pdf.setTextColor(255, 255, 255);
      pdf.text(
        `${getRiskLabel(scorePct)} · ${scorePct.toFixed(1)}%`,
        PW / 2,
        PH / 2 + 10.5,
        { align: "center" }
      );

      // Meta information (User, Date, Grid Count)
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(9);
      pdf.setTextColor(148, 163, 184);
      const meta = [
        `Prepared for: ${userName}`,
        `Analysis Period: ${analysis.start_date ?? "N/A"} → ${analysis.end_date ?? "N/A"}`,
        `Grid cells analysed: ${(analysis.grid ?? []).length}`,
        `Generated: ${new Date().toLocaleString("en-GB")}`,
      ];
      meta.forEach((line, i) =>
        pdf.text(line, PW / 2, PH - 50 + i * 6.5, { align: "center" })
      );

      drawFooter(pdf, PW, PH, pageNum);

      // ==================================================================
      // PAGE 2 — EXECUTIVE SUMMARY & SPATIAL MAP
      // ==================================================================
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Executive Summary & Map");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "1. Executive Summary", 24);

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(9);
      pdf.setTextColor(51, 65, 85);
      const summary =
        "WindGuard assesses wind-induced soil erosion risk using an optimized XGBoost surrogate model integrated with " +
        "Google Earth Engine (GEE). The model incorporates multi-spectral satellite imagery and hourly meteorological data " +
        "to evaluate topsoil vulnerability and vegetation drag coefficient.";
      pdf.text(pdf.splitTextToSize(summary, 180), 15, 31);

      // Risk score highlight box in summary
      pdf.setFillColor(248, 250, 252);
      pdf.setDrawColor(rr, rg, rb);
      pdf.setLineWidth(0.8);
      pdf.roundedRect(15, 43, 180, 12, 2, 2, "FD");
      
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(9.5);
      pdf.setTextColor(rr, rg, rb);
      pdf.text(`Overall Regional Risk Index: ${scorePct.toFixed(1)}% (${getRiskLabel(scorePct)})`, 20, 50.5);

      sectionHeading(pdf, "2. Spatial Risk Map", 64);

      const mapEl = document.querySelector(".leaflet-container");
      if (mapEl) {
        if (mapRef?.current) {
          try {
            mapRef.current.invalidateSize();
            mapRef.current.fitBounds(mapRef.current.getBounds(), { padding: [10, 10] });
          } catch (_) {}
        }
        await new Promise((r) => setTimeout(r, 800));

        try {
          const canvas = await html2canvas(mapEl, {
            useCORS: true,
            scale: 1.5,
            logging: false,
            allowTaint: true,
          });
          const imgData = canvas.toDataURL("image/png");
          pdf.addImage(imgData, "PNG", 15, 70, 180, 100);
        } catch (err) {
          pdf.rect(15, 70, 180, 100);
          pdf.text("Spatial map rendering unavailable", 20, 80);
        }
      }

      // ==================================================================
      // PAGE 3 — HOTSPOT ANALYSIS
      // ==================================================================
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Hotspot Analysis");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "3. Critical Hotspot Identification", 24);

      let hotspotsData = [];
      if (Array.isArray(analysis.hotspots) && analysis.hotspots.length > 0) {
        hotspotsData = analysis.hotspots;
      } else if (Array.isArray(analysis.grid) && analysis.grid.length > 0) {
        hotspotsData = [...analysis.grid]
          .filter((c) => typeof c.risk === "number" && !isNaN(c.risk))
          .sort((a, b) => b.risk - a.risk)
          .slice(0, 10);
      }

      const hotspotRows = hotspotsData.slice(0, 10).map((spot, i) => {
        const rawVal = spot.risk ?? spot.avg_risk ?? spot.risk_score ?? 0;
        const pct = normalizeRiskScore(rawVal);

        let status = "Elevated";
        if (pct >= 60) status = "Critical";
        else if (pct >= 30) status = "High Alert";

        return [
          `#${i + 1}`,
          typeof spot.lat === "number" ? `${spot.lat.toFixed(5)}° N` : "N/A",
          typeof spot.lon === "number" ? `${spot.lon.toFixed(5)}° E` : "N/A",
          `${pct.toFixed(1)}%`,
          status,
        ];
      });

      autoTable(pdf, {
        startY: 30,
        head: [["#", "Latitude", "Longitude", "Risk Score", "Status"]],
        body: hotspotRows.length > 0 ? hotspotRows : [["—", "—", "—", "—", "No hotspots detected"]],
        theme: "striped",
        headStyles: { fillColor: [15, 23, 42], fontSize: 9, fontStyle: "bold" },
        styles: { fontSize: 8.5 },
        columnStyles: { 0: { halign: "center" }, 3: { halign: "center" }, 4: { halign: "center" } },
      });

      // ==================================================================
      // PAGE 4 — FEATURE IMPORTANCE & AI RECOMMENDATIONS
      // ==================================================================
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Feature Importance & AI");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "4. Model Feature Importance (SHAP)", 24);

      const barStartY = 32;
      const maxBarW = 95;
      const totalWeight = REAL_FEATURE_IMPORTANCE.reduce((s, f) => s + f.weight, 0);

      REAL_FEATURE_IMPORTANCE.forEach((feat, idx) => {
        const y = barStartY + idx * 9.5;
        const normalised = feat.weight / totalWeight;
        const activeW = normalised * maxBarW;

        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(8);
        pdf.setTextColor(30, 41, 59);
        pdf.text(feat.name, 15, y + 4.5);

        // Background progress bar
        pdf.setFillColor(226, 232, 240);
        pdf.roundedRect(75, y, maxBarW, 5, 1, 1, "F");

        // Active progress bar
        pdf.setFillColor(...feat.color);
        pdf.roundedRect(75, y, activeW, 5, 1, 1, "F");

        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(8);
        pdf.text(`${feat.weight.toFixed(1)}%`, 75 + maxBarW + 4, y + 4.2);
      });

      const recY = barStartY + REAL_FEATURE_IMPORTANCE.length * 9.5 + 8;
      sectionHeading(pdf, "5. AI Recommendations", recY);

      let cleanAI = aiResponse
        ? aiResponse.replace(/[*#`_~]/g, "").trim()
        : "1. VEGETATION RESTORATION: Establish perennial cover crops in high-risk cells where NDVI falls below regional baseline.\n\n" +
          "2. NO-TILL FARMING: Avoid mechanical tillage during dry spring months (March–May) to prevent topsoil detachment.\n\n" +
          "3. WINDBREAK SHELTERBELTS: Plant Saxaul (Haloxylon ammodendron) perpendicular to prevailing winds.\n\n" +
          "4. TARGETED IRRIGATION: Apply preemptive soil moisture management before high-wind events.";

      pdf.setFillColor(248, 250, 252);
      pdf.roundedRect(15, recY + 6, 180, 85, 2, 2, "F");

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(8.5);
      pdf.setTextColor(30, 41, 59);
      pdf.text(pdf.splitTextToSize(cleanAI, 172), 19, recY + 12);

      // ==================================================================
      // PAGE 5 — METHODOLOGY & DATA PROVENANCE
      // ==================================================================
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Methodology & Provenance");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "6. Data Provenance & Methodology", 24);

      autoTable(pdf, {
        startY: 30,
        head: [["Dataset", "Variable(s)", "Resolution", "Provider"]],
        body: [
          ["Sentinel-5P TROPOMI", "Absorbing Aerosol Index (AAI)", "1.1 km", "ESA"],
          ["MODIS MOD13A2", "NDVI Vegetation Index", "1 km", "NASA LP DAAC"],
          ["ERA5-Land Hourly", "Wind vectors (u/v), Soil Moisture", "9 km", "ECMWF"],
          ["SRTM GL1", "Elevation / Slope", "30 m", "USGS"],
        ],
        theme: "striped",
        headStyles: { fillColor: [15, 23, 42], fontSize: 8.5 },
        styles: { fontSize: 8 },
      });

      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(10);
      pdf.setTextColor(15, 23, 42);
      pdf.text("Scientific References", 15, 82);

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(8);
      pdf.setTextColor(71, 85, 105);
      const refs = [
        "• Fryrear, D. W., et al. (1998). Empirical Wind Erosion Modeling: Revised Wind Erosion Equation (RWEQ).",
        "• Copernicus Climate Change Service (C3S). ERA5-Land hourly data from 1950 to present.",
        "• Herman, J. R., et al. (1997). Global distribution of UV-absorbing aerosols from TOMS data.",
      ];
      refs.forEach((ref, idx) => {
        pdf.text(ref, 15, 90 + idx * 6);
      });

      // ==================================================================
      // PAGE 6 — TECHNICAL APPENDIX (GRID MATRIX)
      // ==================================================================
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Technical Appendix");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "7. Grid Matrix Array (Top 30 Cells)", 24);

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
        startY: 30,
        head: [["Rank", "Latitude", "Longitude", "Risk Score", "Grid Matrix Index"]],
        body: gridRows.length > 0 ? gridRows : [["—", "—", "—", "—", "No grid data"]],
        theme: "grid",
        headStyles: { fillColor: [15, 23, 42], fontSize: 8.5 },
        styles: { fontSize: 7.5 },
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
      {exporting ? "⏳ Generating report…" : "⬇ Download PDF Report"}
    </button>
  );
}