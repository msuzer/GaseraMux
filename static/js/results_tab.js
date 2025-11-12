// ============================================================
// Results Tab – Live Chart Rendering
// ============================================================
// console.log("[results_tab] loaded");

let trackVisibility = {};
let lastStamp = null;
let lastSeenTs = null;
const MAX_POINTS = 100;

const ctx = document.getElementById("liveChart")?.getContext("2d");
window.liveChart = new Chart(ctx, {
  type: "line",
  data: { labels: [], datasets: [] },
  options: {
    responsive: true,
    animation: false,
    scales: {
      x: { title: { display: true, text: "Time" } },
      y: { title: { display: true, text: "PPM" }, beginAtZero: true }
    },
    plugins: {
      zoom: { zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: "x" }, pan: { enabled: true, mode: "x" } },
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
          safeFetch(API_PATHS?.settings?.update, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ track_visibility: trackVisibility })
          });
        }
      }
    }
  }
});

function renderTrackToggles() {
  const container = document.getElementById("trackToggles");
  container.innerHTML = "";
  window.liveChart.data.datasets.forEach((ds, i) => {
    const label = ds.label;
    const id = `track-toggle-${i}`;
    const checked = !ds.hidden;
    const div = document.createElement("div");
    div.classList.add("form-check", "form-switch");
    div.innerHTML = `
      <input class="form-check-input" type="checkbox" id="${id}" ${checked ? "checked" : ""}>
      <div style="display:flex;align-items:center;gap:6px;">
        <span style="width:12px;height:12px;background:${ds.borderColor};display:inline-block;border-radius:2px;"></span>
        <label class="form-check-label" for="${id}" style="color:${ds.borderColor};margin:0;">${label}</label>
      </div>`;
    div.querySelector("input").addEventListener("change", e => {
      const visible = e.target.checked;
      window.liveChart.data.datasets[i].hidden = !visible;
      trackVisibility[label] = visible;
      window.liveChart.update();
      safeFetch(API_PATHS?.settings?.update, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track_visibility: trackVisibility })
      });
    });
    container.appendChild(div);
  });
}

function onLiveUpdate(d) {
  if (!d.live_data?.components) return;
  let ts = d.live_data.timestamp ?? Date.now() / 1000;
  if (typeof ts === "string") ts = Date.parse(ts.replace(" ", "T")) / 1000;
  if (ts && ts === lastSeenTs) return;
  lastSeenTs = ts;

  const label = new Date(ts * 1000).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  const components = Object.entries(d.live_data.components).map(([label, ppm]) => ({ label, ppm }));
  updateChart(label, components);
}

function updateChart(label, components) {
  const isDuplicate = (lastStamp !== null && label === lastStamp);
  let addedDataset = false;
  if (!isDuplicate) {
    window.liveChart.data.labels.push(label);
    if (window.liveChart.data.labels.length > MAX_POINTS) window.liveChart.data.labels.shift();
    window.liveChart.data.datasets.forEach(ds => {
      ds.data.push(null);
      if (ds.data.length > MAX_POINTS) ds.data.shift();
    });
  }
  const idx = window.liveChart.data.labels.length - 1;
  components.forEach(c => {
    let ds = window.liveChart.data.datasets.find(d => d.label === c.label);
    if (!ds) {
      ds = { label: c.label, data: new Array(window.liveChart.data.labels.length).fill(null), hidden: trackVisibility[c.label] === false, borderColor: c.color || undefined, tension: 0.3 };
      window.liveChart.data.datasets.push(ds);
      addedDataset = true;
    }
    ds.data[idx] = c.ppm;
  });
  if (addedDataset) renderTrackToggles();
  window.liveChart.update();
  lastStamp = label;
}

// Save chart/CSV buttons
window.downloadImage = function () {
  const link = document.createElement("a");
  link.href = window.liveChart.toBase64Image();
  const now = new Date().toISOString().replace(/[:T-]/g, "_").split(".")[0];
  link.download = `gasera_chart_${now}.png`;
  link.click();
};

window.downloadCSV = function () {
  if (window.liveChart.data.datasets.length === 0) return;
  let csv = "Time," + window.liveChart.data.datasets.map(d => d.label).join(",") + "\n";
  for (let i = 0; i < window.liveChart.data.labels.length; i++) {
    const row = [window.liveChart.data.labels[i]];
    window.liveChart.data.datasets.forEach(ds => row.push(ds.data[i] ?? ""));
    csv += row.join(",") + "\n";
  }
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  const now = new Date().toISOString().replace(/[:T-]/g, "_").split(".")[0];
  link.download = `gasera_data_${now}.csv`;
  link.click();
};

// Subscribe to SSE
document.addEventListener("DOMContentLoaded", () => {
  window.GaseraHub?.subscribe(onLiveUpdate);
  renderTrackToggles();
  // console.log("[results_livechart] Subscribed to SSE for live updates");
});
