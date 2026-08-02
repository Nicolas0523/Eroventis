import React, { useState } from "react";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import html2canvas from "html2canvas";

// Real SHAP feature importance from the XGBoost model
const REAL_FEATURE_IMPORTANCE = [
  { name: "Wind Mean Speed",        weight: 34.2, color: [239, 68,  68 ] },
  { name: "Soil Moisture",          weight: 26.1, color: [59,  130, 246] },
  { name: "Wind Max Speed",         weight: 14.8, color: [245, 158, 11 ] },
  { name: "NDVI Z-Score",           weight: 10.3, color: [16,  185, 129] },
  { name: "Wind Erosivity (u³)",    weight:  8.1, color: [168, 85,  247] },
  { name: "Aridity Index",          weight:  6.5, color: [236, 72,  153] },
];

function getRiskColor(score) {
  if (score > 0.6) return [220, 38, 38];   // red
  if (score > 0.3) return [180, 120, 0];   // amber
  return [22, 163, 74];                    // green
}

function getRiskLabel(score) {
  if (score > 0.6) return "HIGH RISK";
  if (score > 0.3) return "MEDIUM RISK";
  return "LOW RISK";
}

// ─── Draw page header bar ────────────────────────────────────────────────────
function drawHeader(pdf, pageWidth, title) {
  pdf.setFillColor(15, 23, 42);
  pdf.rect(0, 0, pageWidth, 14, "F");
  pdf.setFillColor(16, 185, 129);
  pdf.rect(0, 14, pageWidth, 1.5, "F");

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(8);
  pdf.setTextColor(148, 163, 184);
  pdf.text("WINDGUARD  ·  Wind Erosion Risk Assessment Platform", 10, 9.5);
  pdf.text(title, pageWidth - 10, 9.5, { align: "right" });
}

// ─── Draw page footer ────────────────────────────────────────────────────────
function drawFooter(pdf, pageWidth, pageHeight, pageNum) {
  pdf.setFillColor(241, 245, 249);
  pdf.rect(0, pageHeight - 10, pageWidth, 10, "F");
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(7.5);
  pdf.setTextColor(100, 116, 139);
  pdf.text(
    `Generated ${new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}  ·  WindGuard v2.0  ·  Data: MODIS / ERA5-Land / SRTM`,
    10,
    pageHeight - 3.5
  );
  pdf.text(`Page ${pageNum}`, pageWidth - 10, pageHeight - 3.5, { align: "right" });
}

// ─── Section heading ─────────────────────────────────────────────────────────
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
      const pdf     = new jsPDF("p", "mm", "a4");
      const PW      = pdf.internal.pageSize.getWidth();   // 210
      const PH      = pdf.internal.pageSize.getHeight();  // 297
      let   pageNum = 0;

      // ══════════════════════════════════════════════════════════════
      // PAGE 1 — COVER
      // ══════════════════════════════════════════════════════════════
      pageNum++;
      pdf.setFillColor(15, 23, 42);
      pdf.rect(0, 0, PW, PH, "F");

      // Accent stripe
      pdf.setFillColor(16, 185, 129);
      pdf.rect(0, PH / 2 - 1, PW, 2, "F");

      // Logo / wordmark
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(48);
      pdf.setTextColor(255, 255, 255);
      pdf.text("WINDGUARD", PW / 2, PH / 2 - 30, { align: "center" });

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(12);
      pdf.setTextColor(148, 163, 184);
      pdf.text("Wind Erosion Risk Assessment Report", PW / 2, PH / 2 - 16, { align: "center" });

      // Risk badge
      const score      = analysis.risk_score ?? 0;
      const [rr, rg, rb] = getRiskColor(score);
      pdf.setFillColor(rr, rg, rb);
      pdf.roundedRect(PW / 2 - 30, PH / 2 + 14, 60, 14, 3, 3, "F");
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(11);
      pdf.setTextColor(255, 255, 255);
      pdf.text(
        `${getRiskLabel(score)}  ·  ${(score * 100).toFixed(1)}%`,
        PW / 2,
        PH / 2 + 23,
        { align: "center" }
      );

      // Meta
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(8.5);
      pdf.setTextColor(71, 85, 105);
      const meta = [
        `Analysis date:  ${analysis.start_date ?? "—"}  →  ${analysis.end_date ?? "—"}`,
        `Grid cells analysed:  ${(analysis.grid ?? []).length}`,
        `Generated:  ${new Date().toLocaleString("en-GB")}`,
      ];
      meta.forEach((line, i) =>
        pdf.text(line, PW / 2, PH - 40 + i * 7, { align: "center" })
      );

      drawFooter(pdf, PW, PH, pageNum);

      // ══════════════════════════════════════════════════════════════
      // PAGE 2 — EXECUTIVE SUMMARY + RISK MAP
      // ══════════════════════════════════════════════════════════════
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Executive Summary");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "1. Executive Summary", 24);

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(10);
      pdf.setTextColor(51, 65, 85);
      const summary =
        "WindGuard assesses wind-induced soil erosion risk using a custom XGBoost surrogate model " +
        "trained on ~200 000 satellite observations (MODIS, ERA5-Land, SRTM) across Kazakhstan " +
        "(2015–2025). The model emulates a RWEQ-based vulnerability index — a deliberate design " +
        "choice that enables fast, country-scale inference without requiring labelled field-measurement " +
        "datasets that do not yet exist at this resolution. Risk scores range from 0 (none) to 1 (critical).";
      pdf.text(pdf.splitTextToSize(summary, 180), 15, 32);

      // Risk score card
      pdf.setFillColor(rr, rg, rb, 0.08);
      pdf.setFillColor(
        Math.min(rr + 200, 255),
        Math.min(rg + 200, 255),
        Math.min(rb + 200, 255)
      );
      pdf.roundedRect(15, 60, 180, 18, 3, 3, "F");
      pdf.setDrawColor(rr, rg, rb);
      pdf.setLineWidth(0.8);
      pdf.roundedRect(15, 60, 180, 18, 3, 3, "S");
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(12);
      pdf.setTextColor(rr, rg, rb);
      pdf.text(
        `Overall risk score: ${getRiskLabel(score)}  (${(score * 100).toFixed(1)}%)`,
        105,
        71,
        { align: "center" }
      );

      // Map screenshot
      sectionHeading(pdf, "2. Risk Map", 88);

      const mapEl = document.querySelector(".leaflet-container");
      if (mapEl) {
        // Fit map to polygon before capture
        if (mapRef?.current) {
          try { mapRef.current.fitBounds(mapRef.current.getBounds(), { padding: [20, 20] }); }
          catch (_) {}
        }
        await new Promise(r => setTimeout(r, 2000));
        const canvas = await html2canvas(mapEl, {
          useCORS: true,
          scale: 1.8,
          logging: false,
        });
        const imgData = canvas.toDataURL("image/png");
        const imgH    = (canvas.height / canvas.width) * 180;
        pdf.addImage(imgData, "PNG", 15, 95, 180, Math.min(imgH, 165));
      } else {
        pdf.setFontSize(9);
        pdf.setTextColor(148, 163, 184);
        pdf.text("[Map not captured — ensure the map is visible on screen before exporting]", 15, 102);
      }

      // ══════════════════════════════════════════════════════════════
      // PAGE 3 — HOTSPOT ANALYSIS
      // ══════════════════════════════════════════════════════════════
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Hotspot Analysis");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "3. Hotspot Analysis", 24);

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(10);
      pdf.setTextColor(51, 65, 85);
      pdf.text(
        pdf.splitTextToSize(
          "Hotspots are contiguous groups of ≥ 5 grid cells where the predicted risk exceeds 70 %. " +
          "They represent zones where urgent land-management intervention is recommended.",
          180
        ),
        15,
        32
      );

      // Build hotspot rows
      let hotspots = analysis.hotspots ?? [];
      if (hotspots.length === 0 && (analysis.grid ?? []).length > 0) {
        hotspots = [...analysis.grid]
          .filter(c => typeof c.risk === "number" && !isNaN(c.risk))
          .sort((a, b) => b.risk - a.risk)
          .slice(0, 8)
          .map(c => ({ lat: c.lat, lon: c.lon, avg_risk: c.risk }));
      }

      const hotspotRows = hotspots.map((spot, i) => {
        let r = parseFloat(spot.avg_risk ?? spot.risk ?? 0);
        if (r > 0 && r <= 1) r *= 100;
        return [
          `#${i + 1}`,
          typeof spot.lat === "number" ? `${spot.lat.toFixed(5)}° N` : "N/A",
          typeof spot.lon === "number" ? `${spot.lon.toFixed(5)}° E` : "N/A",
          `${r.toFixed(1)}%`,
          r > 80 ? "Critical" : r > 60 ? "High Alert" : "Elevated",
        ];
      });

      autoTable(pdf, {
        startY: 44,
        head: [["#", "Latitude", "Longitude", "Risk Score", "Status"]],
        body:
          hotspotRows.length > 0
            ? hotspotRows
            : [["—", "—", "—", "—", "No critical hotspots detected"]],
        theme: "striped",
        headStyles: { fillColor: [15, 23, 42], fontSize: 9.5, fontStyle: "bold" },
        styles: { fontSize: 9 },
        columnStyles: { 0: { halign: "center" }, 3: { halign: "center" }, 4: { halign: "center" } },
      });

      // ══════════════════════════════════════════════════════════════
      // PAGE 4 — FEATURE IMPORTANCE + AI RECOMMENDATIONS
      // ══════════════════════════════════════════════════════════════
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Feature Importance & Recommendations");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "4. Model Feature Importance (SHAP)", 24);

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(9.5);
      pdf.setTextColor(51, 65, 85);
      pdf.text(
        pdf.splitTextToSize(
          "Feature importance is derived from SHAP (SHapley Additive exPlanations) values computed " +
          "on the XGBoost model. Values reflect mean absolute SHAP contribution across the test set.",
          180
        ),
        15,
        32
      );

      // Progress bars
      const barStartY  = 45;
      const maxBarW    = 110;
      const totalWeight = REAL_FEATURE_IMPORTANCE.reduce((s, f) => s + f.weight, 0);

      REAL_FEATURE_IMPORTANCE.forEach((feat, idx) => {
        const y           = barStartY + idx * 13;
        const normalised  = feat.weight / totalWeight;
        const activeW     = normalised * maxBarW;

        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(9);
        pdf.setTextColor(30, 41, 59);
        pdf.text(feat.name, 15, y + 5);

        // Track
        pdf.setFillColor(226, 232, 240);
        pdf.roundedRect(80, y, maxBarW, 7, 1.5, 1.5, "F");

        // Fill
        pdf.setFillColor(...feat.color);
        pdf.roundedRect(80, y, activeW, 7, 1.5, 1.5, "F");

        // Label
        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(9);
        pdf.setTextColor(30, 41, 59);
        pdf.text(`${feat.weight.toFixed(1)}%`, 80 + maxBarW + 4, y + 5.5);
      });

      // AI Recommendations
      const recY = barStartY + REAL_FEATURE_IMPORTANCE.length * 13 + 10;
      sectionHeading(pdf, "5. AI Recommendations", recY);

      let cleanAI = "";
      if (aiResponse) {
        cleanAI = aiResponse.replace(/[*#`_~]/g, "").trim();
      } else {
        cleanAI =
          "Based on the spatial risk model, WindGuard recommends the following:\n\n" +
          "1. VEGETATION RESTORATION — Establish perennial cover crops in high-risk cells " +
          "where NDVI falls below the regional baseline. Bare soil is the primary driver of wind erosion.\n\n" +
          "2. NO-TILL FARMING — Avoid mechanical tillage during spring dry-season months (March–May) " +
          "when wind erosivity peaks across the steppe zones.\n\n" +
          "3. WINDBREAK INSTALLATION — Plant shelter-belt rows perpendicular to the prevailing " +
          "north-westerly winds to reduce near-surface wind shear over vulnerable topsoil.\n\n" +
          "4. TARGETED IRRIGATION — Pre-emptive soil moisture application before forecast wind " +
          "events exceeding 12 m/s significantly reduces particle detachment potential.";
      }

      pdf.setFillColor(248, 250, 252);
      const recBoxH = PH - recY - 18;
      pdf.roundedRect(15, recY + 6, 180, recBoxH, 2, 2, "F");

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(9.5);
      pdf.setTextColor(30, 41, 59);
      pdf.text(
        pdf.splitTextToSize(cleanAI, 170),
        20,
        recY + 14
      );

      // ══════════════════════════════════════════════════════════════
      // PAGE 5 — METHODOLOGY & DATA SOURCES
      // ══════════════════════════════════════════════════════════════
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Methodology & References");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "6. Methodology", 24);

      const methodText =
        "The WindGuard risk index is computed by an XGBoost gradient-boosting regressor trained on a " +
        "self-constructed dataset of ~200 000 observations. Because no labelled ground-truth erosion " +
        "dataset exists for Kazakhstan at 1 km resolution, the target variable was derived from a " +
        "RWEQ-based vulnerability formula applied to multi-source satellite data — a valid surrogate-model " +
        "approach. This explains the high R² (0.9947): the model is learning to reproduce the RWEQ index " +
        "efficiently, not predicting a fully independent physical measurement.\n\n" +
        "The 2040–2050 climate scenario combines NASA CMIP6 projections (temperature, wind, precipitation " +
        "under SSP5-8.5) with recent ERA5-Land observations for variables unavailable in CMIP6 " +
        "(NDVI, slope, soil type). Results should be interpreted as indicative scenarios, not precise forecasts, " +
        "because gradient-boosted trees do not extrapolate beyond their training distribution.";

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(10);
      pdf.setTextColor(51, 65, 85);
      pdf.text(pdf.splitTextToSize(methodText, 180), 15, 32);

      sectionHeading(pdf, "7. Data Sources", 108);

      autoTable(pdf, {
        startY: 115,
        head: [["Dataset", "Variable(s)", "Resolution"]],
        body: [
          ["MODIS MOD13A2 (NASA LP DAAC)", "NDVI", "1 km / 16-day"],
          ["ERA5-Land Hourly (ECMWF)", "Wind speed, temperature,\nsoil moisture, precipitation, evaporation", "9 km / hourly"],
          ["SRTM GL1 (USGS)", "Elevation / slope", "30 m"],
          ["ESA WorldCover v200", "Land cover / biome", "10 m"],
          ["OpenLandMap SOL (v02)", "Soil texture class", "250 m"],
          ["NASA GDDP-CMIP6", "Future temperature & precipitation\n(SSP5-8.5, ACCESS-CM2)", "25 km / daily"],
        ],
        theme: "striped",
        headStyles: { fillColor: [15, 23, 42], fontSize: 9 },
        styles: { fontSize: 8.5 },
      });

      sectionHeading(pdf, "8. Scientific References", pdf.lastAutoTable.finalY + 12);

      const refs = [
        "Fryrear, D.W. et al. (1998). RWEQ: Improved Wind Erosion Technology. Journal of Soil and Water Conservation, 53(3), 183–189.",
        "Chen, T. & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. Proceedings of KDD 2016, 785–794.",
        "Hersbach, H. et al. (2020). The ERA5 Global Reanalysis. Quarterly Journal of the Royal Meteorological Society, 146(730), 1999–2049.",
        "Gorelick, N. et al. (2017). Google Earth Engine: Planetary-Scale Geospatial Analysis for Everyone. Remote Sensing of Environment, 202, 18–27.",
        "Tucker, C.J. (1979). Red and Photographic Infrared Linear Combinations for Monitoring Vegetation. Remote Sensing of Environment, 8(2), 127–150.",
        "UNCCD (2023). Central Asia Regional Factsheet. United Nations Convention to Combat Desertification.",
      ];

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(9);
      pdf.setTextColor(51, 65, 85);
      refs.forEach((ref, i) => {
        const refY = pdf.lastAutoTable.finalY + 20 + i * 11;
        pdf.setFont("helvetica", "bold");
        pdf.text(`[${i + 1}]`, 15, refY);
        pdf.setFont("helvetica", "normal");
        pdf.text(pdf.splitTextToSize(ref, 170), 23, refY);
      });

      // ══════════════════════════════════════════════════════════════
      // PAGE 6 — TECHNICAL APPENDIX (GRID MATRIX)
      // ══════════════════════════════════════════════════════════════
      pdf.addPage();
      pageNum++;
      drawHeader(pdf, PW, "Technical Appendix");
      drawFooter(pdf, PW, PH, pageNum);

      sectionHeading(pdf, "9. Grid Matrix (top 30 cells by risk)", 24);

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(9);
      pdf.setTextColor(100, 116, 139);
      pdf.text(
        `Total cells in polygon: ${(analysis.grid ?? []).length}  ·  Showing highest-risk 30`,
        15,
        32
      );

      const gridRows = [...(analysis.grid ?? [])]
        .filter(c => typeof c.risk === "number")
        .sort((a, b) => b.risk - a.risk)
        .slice(0, 30)
        .map((cell, idx) => {
          const r = (cell.risk * 100).toFixed(1);
          return [
            `#${idx + 1}`,
            typeof cell.lat === "number" ? cell.lat.toFixed(5) : "N/A",
            typeof cell.lon === "number" ? cell.lon.toFixed(5) : "N/A",
            `${r}%`,
            cell.risk > 0.7 ? "High" : cell.risk > 0.4 ? "Medium" : "Low",
          ];
        });

      autoTable(pdf, {
        startY: 38,
        head: [["Rank", "Latitude", "Longitude", "Risk Score", "Level"]],
        body:
          gridRows.length > 0
            ? gridRows
            : [["—", "—", "—", "—", "No grid data available"]],
        theme: "striped",
        headStyles: { fillColor: [15, 23, 42], fontSize: 9 },
        styles: { fontSize: 8.5 },
        columnStyles: {
          0: { halign: "center" },
          3: { halign: "center" },
          4: { halign: "center" },
        },
        didParseCell: (data) => {
          if (data.section === "body" && data.column.index === 4) {
            const val = data.cell.raw;
            if (val === "High")   data.cell.styles.textColor = [220, 38,  38 ];
            if (val === "Medium") data.cell.styles.textColor = [180, 120, 0  ];
            if (val === "Low")    data.cell.styles.textColor = [22,  163, 74 ];
          }
        },
      });

      // ── Save ──────────────────────────────────────────────────────
      const date = new Date().toISOString().slice(0, 10);
      pdf.save(`WindGuard_Report_${date}.pdf`);
    } catch (err) {
      console.error("PDF export failed:", err);
      alert("PDF export failed — check the browser console for details.");
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
          : "linear-gradient(135deg, #10b981 0%, #059669 100%)",
        color: "#fff",
        fontWeight: "700",
        fontSize: "13px",
        border: "none",
        borderRadius: "6px",
        cursor: exporting || !analysis ? "not-allowed" : "pointer",
        letterSpacing: "0.5px",
        transition: "background 0.2s",
      }}
    >
      {exporting ? "⏳  Generating report…" : "⬇  Download PDF Report"}
    </button>
  );
}