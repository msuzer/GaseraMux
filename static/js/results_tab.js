// ============================================================
// Results Tab – Live Chart Rendering
// ============================================================
// console.log("[results_tab] loaded");

const MAX_POINTS = 100;

let trackVisibility = {};

// Gas colors tuned for brighter, higher-saturation palette (old app style)
const GAS_COLORS = {
  // Core gases seen in screenshot
  "Ammonia (NH₃, 7664-41-7)": "#1f77b4",        // vivid blue
  "Carbon Dioxide (CO₂, 124-38-9)": "#ff6384",  // bright pink/red
  "Methane (CH₄, 74-82-8)": "#ff9f40",          // bright orange
  "Nitrous Oxide (N₂O, 10024-97-2)": "#ffcd56", // bright yellow
  "Water Vapor (H₂O, 7732-18-5)": "#2ca02c",    // vivid green/teal

  // Additional typical gases (kept vivid Chart.js-like palette)
  "Carbon Monoxide (CO, 630-08-0)": "#d62728",
  "Sulfur Dioxide (SO₂, 7446-09-5)": "#e377c2",
  "Oxygen (O₂, 7782-44-7)": "#7f7f7f",
  "Acetaldehyde (CH₃CHO, 75-07-0)": "#bcbd22",
  "Ethanol (C₂H₅OH, 64-17-5)": "#17becf",
  "Methanol (CH₃OH, 67-56-1)": "#a05d56"
};

window.chartMode = "live";   // "live" | "csv"
window.currentCSV = null;
window.lastSSEPhase = "IDLE";

window.chartMeta = {
  phase: [],
  channel: [],
  repeat: []
};

const ctx = document.getElementById("liveChart")?.getContext("2d");
window.liveChart = new Chart(ctx, {
  type: "line",
  data: { labels: [], datasets: [] },
  options: {
    responsive: true,
    animation: false,
    spanGaps: true,
    normalized: true,
    parsing: true, // enable built-in parsing, otherwise Chart.js v4 fails to parse nulls properly
    scales: {
      x: {
        title: { display: true, text: "Time" },
        type: "category",
        ticks: { source: "data" },
        offset: false
      },
      y: { title: { display: true, text: "PPM" }, beginAtZero: true }
    },
    plugins: {
      zoom: {
        zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: "x" },
        pan: { enabled: true, mode: "x" }
      },

      // --------------------------------------------------------------
      // TOOLTIP ENHANCEMENT (phase, channel, repeat)
      // --------------------------------------------------------------
      tooltip: {
        callbacks: {
          // Title: timestamp
          title: function (ctx) {
            return ctx[0].label;
          },

          // Label: component + ppm + metadata (phase/channel/repeat)
          label: function (ctx) {
            const comp = ctx.dataset.label;
            const ppm = ctx.parsed.y;
            const idx = ctx.dataIndex;

            // Retrieve metadata if present
            const phase = window.chartMeta.phase[idx] ?? null;
            const channel = window.chartMeta.channel[idx] ?? null;
            const repeat = window.chartMeta.repeat[idx] ?? null;

            const lines = [`${comp}: ${ppm} ppm`];

            // Only show metadata if present
            if (phase != null) lines.push(`Phase: ${phase}`);
            if (channel != null) lines.push(`Channel: ${channel}`);
            if (repeat != null) lines.push(`Repeat: ${repeat}`);

            return lines;
          }
        }
      },

      legend: {
        onClick: function (e, legendItem, legend) {
          const index = legendItem.datasetIndex;
          const chart = legend.chart;
          const label = chart.data.datasets[index].label;
          const meta = chart.getDatasetMeta(index);
          meta.hidden = meta.hidden == null ? !chart.data.datasets[index].hidden : null;
          chart.update();
          trackVisibility[label] = chart.isDatasetVisible(index);
          const checkbox = document.getElementById(`track-toggle-${index}`);
          if (checkbox) checkbox.checked = trackVisibility[label];
          saveTrackVisibility();
        }
      }
    }
  }
});

function saveTrackVisibility() {
  safeFetch(API_PATHS?.settings?.update, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ track_visibility: trackVisibility })
  });
}

function renderTrackToggles() {
  const container = document.getElementById("trackToggles");
  if (!container) return;
  
  container.innerHTML = "";
  window.liveChart.data.datasets.forEach((ds, i) => {
    const label = ds.label;
    const id = `track-toggle-${i}`;
    const checked = !ds.hidden;
    const div = document.createElement("div");
    div.classList.add("form-check", "form-switch");
    div.innerHTML = `
      <input class="form-check-input" type="checkbox" id="${id}" ${checked ? "checked" : ""}>
      <span style="width:12px;height:12px;background:${ds.borderColor};display:inline-block;border-radius:2px;"></span>
      <label class="form-check-label" for="${id}" style="color:${ds.borderColor};">${label}</label>
    `;
    div.querySelector("input").addEventListener("change", e => {
      const visible = e.target.checked;
      window.liveChart.data.datasets[i].hidden = !visible;
      trackVisibility[label] = visible;
      window.liveChart.update();
      saveTrackVisibility();
    });
    container.appendChild(div);
  });
}

// Save chart/CSV buttons
window.downloadImage = function () {
  const link = document.createElement("a");
  link.href = window.liveChart.toBase64Image();
  const now = new Date().toISOString().replace(/[:T-]/g, "_").split(".")[0];
  link.download = `gasera_chart_${now}.png`;
  link.click();
};

// --------------------------------------------------------------------
// Mode UI
// --------------------------------------------------------------------

function resetChart() {
  window.liveChart.data.labels = [];
  window.liveChart.data.datasets = [];
  window.chartMeta.phase = [];
  window.chartMeta.channel = [];
  window.chartMeta.repeat = [];
  window.liveChart.update();
}

function setChartModeUI(mode) {
  const container = document.getElementById("liveChartContainer");
  const notice = document.getElementById("liveNotice");
  
  if (container) {
    container.style.backgroundColor = mode === "live"
      ? "rgba(0,150,0,0.05)"
      : "rgba(150,0,0,0.05)";
  }
  
  if (notice) {
    notice.textContent = mode === "live" 
      ? "Live Mode" 
      : (window.currentCSV ? `Playback Mode: ${window.currentCSV}` : "No CSV Loaded");
  }
}

function updateChartLive(ld) {
  if (!ld || !ld.timestamp || !ld.components) return;
  const chart = window.liveChart;
  const ts = ld.timestamp;

  // ORDER CHECK
  const lastTs = chart.data.labels.at(-1);
  if (lastTs && ts <= lastTs) return;

  // ADD LABEL FIRST
  chart.data.labels.push(ts);

  // Enforce MAX_POINTS limit
  if (chart.data.labels.length > MAX_POINTS) {
    chart.data.labels.shift();
    window.chartMeta.phase.shift();
    window.chartMeta.channel.shift();
    window.chartMeta.repeat.shift();
    chart.data.datasets.forEach(ds => {
      if (ds.data.length > 0) ds.data.shift();
    });
  }

  // ADD META
  window.chartMeta.phase.push(ld.phase);
  window.chartMeta.channel.push(ld.channel);
  window.chartMeta.repeat.push(ld.repeat);

  // PAD EXISTING DATASETS WITH EXACTLY ONE NULL
  chart.data.datasets.forEach(ds => {
    ds.data.push(null);
  });

  const idx = chart.data.labels.length - 1;
  let addedDataset = false;

  // INSERT COMPONENT VALUES
  ld.components.forEach(comp => {
    let ds = chart.data.datasets.find(d => d.label === comp.label);

    if (!ds) {
      // Create dataset aligned with ALL timestamps
      const color = comp.color || GAS_COLORS[comp.label] || `hsl(${Math.random() * 360}, 70%, 50%)`;
      ds = {
        label: comp.label,
        data: new Array(chart.data.labels.length).fill(null),
        hidden: trackVisibility[comp.label] === false,
        borderColor: color,
        backgroundColor: color,
        borderWidth: 2,
        tension: 0.3
      };
      
      chart.data.datasets.push(ds);
      addedDataset = true;
    }

    ds.data[idx] = comp.ppm;
  });

  if (addedDataset) {
    renderTrackToggles();
  }

  chart.update();
}

function updateChartWithWideRows(rows) {
  if (!window.liveChart || !rows || rows.length === 0) return;

  // Sort rows by timestamp ascending
  rows.sort((a, b) => a.timestamp.localeCompare(b.timestamp));

  // Reuse updateChartLive for each row
  rows.forEach(row => {
    updateChartLive(row);
  });
}

function safeSplitCSVLine(line) {
  // Splits tab-delimited lines correctly
  return line.split('\t')
    .map(s => s
      .replace(/^"|"$/g, "")   // remove surrounding quotes
      .replace(/\r$/, "")      // remove trailing CR from Windows CRLF
      .trim()                  // remove whitespace
    )
    .filter(s => s.length > 0); // drop empty columns
}

function parseWideCSV(text) {
  const lines = text.trim().split("\n");
  if (lines.length < 2) return null;

  const header = safeSplitCSVLine(lines[0]);  // FIXED
  const baseCols = ["timestamp", "phase", "channel", "repeat"];
  const compHeaders = header.slice(baseCols.length);

  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;  // skip fully empty line

    const vals = safeSplitCSVLine(line);
    if (vals.length < baseCols.length) continue;   // skip invalid row

    if (!vals[0] || vals[0].trim() === "") continue;  // skip empty timestamp
    if (!vals[1] || vals[1].trim() === "") continue;  // (optional) skip rows missing phase

    const entry = {
      timestamp: vals[0],
      phase: vals[1],
      channel: Number(vals[2]),
      repeat: Number(vals[3]),
      components: []    // Array format required by chart
    };

    let baseIdx = baseCols.length;

    for (let c = 0; c < compHeaders.length; c++) {
      const ppmValue = vals[baseIdx + c];
      entry.components.push({
        label: compHeaders[c],
        ppm: ppmValue === "" ? null : Number(ppmValue)
      });
    }

    rows.push(entry);
  }

  return rows;
}


async function chartLoadCSVSeries(filename) {
  if (window.lastSSEPhase !== "IDLE" && window.lastSSEPhase !== "ABORTED") {
    window.showConfirmModal({
      title: "Device Busy",
      message: "Device is measuring. Cannot show CSV during live measurement.",
      confirmText: "OK",
      cancelText: "",
      confirmClass: "btn-primary",
      headerClass: "bg-warning-subtle"
    });
    return;
  }

  window.chartMode = "csv";
  window.currentCSV = filename;

  try {
    const resp = await fetch(`${API_PATHS?.logs?.download}${filename}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    
    const text = await resp.text();
    const rows = parseWideCSV(text);
    
    if (!rows || rows.length === 0) {
      window.showConfirmModal({
        title: "No Data",
        message: "No valid data found in CSV file.",
        confirmText: "OK",
        cancelText: "",
        confirmClass: "btn-primary",
        headerClass: "bg-warning-subtle"
      });
      switchToLiveMode();
      return;
    }
    
    resetChart();
    updateChartWithWideRows(rows);
    setChartModeUI("csv");
    renderTrackToggles();
  } catch (err) {
    console.error("[results_tab] CSV load failed:", err);
    window.showConfirmModal({
      title: "Load Failed",
      message: `Failed to load CSV: ${err.message}`,
      confirmText: "OK",
      cancelText: "",
      confirmClass: "btn-primary",
      headerClass: "bg-danger-subtle"
    });
    switchToLiveMode();
  }
}

// Expose globally for logs panel
window.chartLoadCSVSeries = chartLoadCSVSeries;

function switchToLiveMode() {
  window.chartMode = "live";
  window.currentCSV = null;
  setChartModeUI("live");
  resetChart();
}

function onSSEEvent(ev) {
  window.lastSSEPhase = ev.phase;

  // Auto return to live when new measurement begins
  if (ev.phase === "MEASURING" && window.chartMode === "csv") {
    switchToLiveMode();
  }

  // Process live data only in live mode
  if (window.chartMode === "live" && ev.live_data?.components) {
    updateChartLive(ev.live_data);
  }
}

// Subscribe to SSE
document.addEventListener("DOMContentLoaded", () => {
  window.GaseraHub?.subscribe(onSSEEvent);
  renderTrackToggles();
  // console.log("[results_livechart] Subscribed to SSE for live updates");
  setChartModeUI("live");
});
