// RoadPulse AI - Interactive Application Logic

let map;
let markerLayerGroup;
let heatLayer;
let routePolyline;
let activeVehicleMarker;
let allClusters = [];
let sampleTrack = [];
let liveSocket = null;
let currentSelectedCluster = null;

const DAMAGE_NAMES = {
  "D00": "Longitudinal Crack",
  "D10": "Transverse Crack",
  "D20": "Alligator Crack",
  "D40": "Pothole / Cavity"
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  initMap();
  initTabs();
  initEventListeners();
  loadStats();
  loadClusters();
  loadSampleTrack();
  loadMunicipalityData();
});

// 1. Leaflet Map Setup
function initMap() {
  const defaultCenter = [12.9730, 77.5960];
  map = L.map('map', {
    center: defaultCenter,
    zoom: 15,
    zoomControl: true
  });

  // Dark CartoDB basemap tiles
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    subdomains: 'abcd',
    maxZoom: 19
  }).addTo(map);

  markerLayerGroup = L.layerGroup().addTo(map);
}

// 2. Tab Navigation
function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const target = document.getElementById(btn.dataset.tab);
      if (target) {
        target.classList.add("active");
        if (btn.dataset.tab === "tab-map" && map) {
          setTimeout(() => map.invalidateSize(), 150);
        }
      }
    });
  });
}

// 3. Event Listeners
function initEventListeners() {
  document.getElementById("btn-refresh-data")?.addEventListener("click", () => {
    loadStats();
    loadClusters();
    loadMunicipalityData();
  });

  document.getElementById("btn-quick-report")?.addEventListener("click", () => {
    const citizenTab = document.querySelector('[data-tab="tab-citizen"]');
    if (citizenTab) citizenTab.click();
  });

  document.getElementById("filter-severity")?.addEventListener("change", renderClusterMarkers);
  document.getElementById("filter-class")?.addEventListener("change", renderClusterMarkers);
  document.getElementById("filter-status")?.addEventListener("change", renderClusterMarkers);
  document.getElementById("search-road")?.addEventListener("input", renderClusterMarkers);

  // Map toolbar toggles
  document.getElementById("btn-toggle-markers")?.addEventListener("click", (e) => {
    const btn = e.currentTarget;
    if (map.hasLayer(markerLayerGroup)) {
      map.removeLayer(markerLayerGroup);
      btn.classList.remove("active");
    } else {
      map.addLayer(markerLayerGroup);
      btn.classList.add("active");
    }
  });

  document.getElementById("btn-toggle-heat")?.addEventListener("click", (e) => {
    const btn = e.currentTarget;
    if (heatLayer) {
      if (map.hasLayer(heatLayer)) {
        map.removeLayer(heatLayer);
        btn.classList.remove("active");
      } else {
        map.addLayer(heatLayer);
        btn.classList.add("active");
      }
    }
  });

  document.getElementById("btn-toggle-route")?.addEventListener("click", (e) => {
    const btn = e.currentTarget;
    if (routePolyline) {
      if (map.hasLayer(routePolyline)) {
        map.removeLayer(routePolyline);
        btn.classList.remove("active");
      } else {
        map.addLayer(routePolyline);
        btn.classList.add("active");
      }
    }
  });

  document.getElementById("btn-recenter-map")?.addEventListener("click", () => {
    if (allClusters.length > 0) {
      const bounds = L.latLngBounds(allClusters.map(c => [c.lat, c.lon]));
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  });

  // Modal controls
  document.getElementById("modal-close")?.addEventListener("click", closeModal);
  document.getElementById("defect-modal")?.addEventListener("click", (e) => {
    if (e.target.id === "defect-modal") closeModal();
  });

  document.getElementById("modal-btn-dispatch")?.addEventListener("click", () => {
    if (currentSelectedCluster) {
      generateComplaintForCluster(currentSelectedCluster.id);
    }
  });

  // Dashcam Studio controls
  document.getElementById("btn-start-simulation")?.addEventListener("click", startLiveDriveSimulation);
  document.getElementById("btn-stop-simulation")?.addEventListener("click", stopLiveDriveSimulation);

  // Citizen Photo Upload
  setupPhotoUpload();
}

// 4. API Loaders
async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();
    document.getElementById("kpi-critical").innerText = data.critical_clusters || 0;
    document.getElementById("kpi-clusters").innerText = data.total_clusters || 0;
    document.getElementById("kpi-dedupe").innerText = `${data.dedupe_ratio_percent || 0}%`;
    document.getElementById("kpi-repaired").innerText = data.repaired_clusters || 0;
  } catch (err) {
    console.error("Failed to load stats:", err);
  }
}

async function loadClusters() {
  try {
    const res = await fetch("/api/clusters");
    allClusters = await res.json();
    renderClusterMarkers();
    renderClusterSideList();
  } catch (err) {
    console.error("Failed to load clusters:", err);
  }
}

async function loadSampleTrack() {
  try {
    const res = await fetch("/api/sample/track");
    sampleTrack = await res.json();
    if (sampleTrack.length > 0) {
      const latlngs = sampleTrack.map(p => [p.lat, p.lon]);
      if (routePolyline) map.removeLayer(routePolyline);
      routePolyline = L.polyline(latlngs, {
        color: '#38bdf8',
        weight: 4,
        opacity: 0.7,
        dashArray: '8, 8'
      }).addTo(map);
    }
  } catch (err) {
    console.error("Failed to load sample track:", err);
  }
}

// 5. Render Map Markers & Heatmap
function renderClusterMarkers() {
  markerLayerGroup.clearLayers();

  const sevFilter = document.getElementById("filter-severity")?.value || "All";
  const clsFilter = document.getElementById("filter-class")?.value || "All";
  const statusFilter = document.getElementById("filter-status")?.value || "All";
  const searchFilter = (document.getElementById("search-road")?.value || "").toLowerCase();

  const filtered = allClusters.filter(c => {
    if (sevFilter !== "All" && c.severity_tier !== sevFilter) return false;
    if (clsFilter !== "All" && c.damage_class !== clsFilter) return false;
    if (statusFilter !== "All" && c.status !== statusFilter) return false;
    if (searchFilter && !c.road_name.toLowerCase().includes(searchFilter)) return false;
    return true;
  });

  const labelEl = document.getElementById("cluster-count-label");
  if (labelEl) labelEl.innerText = `${filtered.length} defects`;

  const heatPoints = [];

  filtered.forEach(c => {
    // Determine pin color class
    let pinClass = "pin-medium";
    let intensity = 0.5;
    if (c.severity_tier === "Critical") { pinClass = "pin-critical"; intensity = 0.95; }
    else if (c.severity_tier === "High") { pinClass = "pin-high"; intensity = 0.75; }
    else if (c.severity_tier === "Low") { pinClass = "pin-low"; intensity = 0.35; }

    heatPoints.push([c.lat, c.lon, intensity]);

    const iconHtml = `<div class="custom-marker-pin ${pinClass}" style="width:26px; height:26px;">!</div>`;
    const customIcon = L.divIcon({
      html: iconHtml,
      className: 'road-pin-container',
      iconSize: [26, 26],
      iconAnchor: [13, 13]
    });

    const marker = L.marker([c.lat, c.lon], { icon: customIcon });

    // Popup content
    const imgUrl = c.image_filename ? (c.image_filename.startsWith("sample_") ? `/data/samples/${c.image_filename}` : `/data/uploads/${c.image_filename}`) : "/data/samples/sample_pothole_d40_crit.jpg";
    const popupContent = `
      <div class="popup-card">
        <div class="popup-img-wrap">
          <img src="${imgUrl}" alt="${c.damage_class}" />
        </div>
        <div class="popup-title">${c.damage_class} - ${c.class_name || DAMAGE_NAMES[c.damage_class]}</div>
        <div class="popup-sub">${c.road_name}</div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
          <span class="tier-badge ${c.severity_tier}">${c.severity_tier} (${c.severity_score})</span>
          <span style="font-size:0.75rem; color:#38bdf8;">${c.detection_count} passes</span>
        </div>
        <button class="btn-primary" style="width:100%; justify-content:center; padding:0.4rem;" onclick="openClusterModal(${c.id})">
          Inspect & Dispatch
        </button>
      </div>
    `;

    marker.bindPopup(popupContent);
    marker.on("click", () => selectClusterInList(c.id));
    markerLayerGroup.addLayer(marker);
  });

  // Re-build heatmap layer
  if (heatLayer) map.removeLayer(heatLayer);
  if (heatPoints.length > 0 && typeof L.heatLayer === "function") {
    heatLayer = L.heatLayer(heatPoints, {
      radius: 28,
      blur: 20,
      maxZoom: 17,
      gradient: { 0.2: '#10b981', 0.5: '#fbbf24', 0.8: '#fb923c', 1.0: '#f43f5e' }
    });
    // Check if heat button is active
    if (document.getElementById("btn-toggle-heat")?.classList.contains("active")) {
      heatLayer.addTo(map);
    }
  }

  renderClusterSideList(filtered);
}

function renderClusterSideList(clusters = allClusters) {
  const container = document.getElementById("cluster-list");
  if (!container) return;
  container.innerHTML = "";

  if (clusters.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted); font-size: 0.8rem; text-align: center; padding: 1rem;">No matching road defects found.</div>`;
    return;
  }

  clusters.forEach(c => {
    const item = document.createElement("div");
    item.className = "cluster-item";
    item.dataset.id = c.id;
    item.innerHTML = `
      <div class="cluster-item-header">
        <span class="tier-badge ${c.severity_tier}">${c.severity_tier} &bull; ${c.severity_score}</span>
        <span style="font-size:0.72rem; color:var(--text-secondary);">${c.status}</span>
      </div>
      <div class="cluster-road">${c.road_name}</div>
      <div class="cluster-meta">
        <span>${c.damage_class} (${c.detection_count} merged)</span>
        <span style="color:var(--accent-cyan); font-weight:600;">$${c.repair_cost_est}</span>
      </div>
    `;
    item.addEventListener("click", () => {
      selectClusterInList(c.id);
      map.setView([c.lat, c.lon], 17);
      openClusterModal(c.id);
    });
    container.appendChild(item);
  });
}

function selectClusterInList(clusterId) {
  document.querySelectorAll(".cluster-item").forEach(el => {
    el.classList.toggle("selected", el.dataset.id == clusterId);
  });
}

// 6. Modal Details & Grievance Generation
window.openClusterModal = function(clusterId) {
  const cluster = allClusters.find(c => c.id == clusterId);
  if (!cluster) return;

  currentSelectedCluster = cluster;
  document.getElementById("modal-title").innerText = `${cluster.damage_class} - ${cluster.class_name || DAMAGE_NAMES[cluster.damage_class]}`;
  document.getElementById("modal-road").innerText = `${cluster.road_name} (${cluster.lat.toFixed(6)}° N, ${cluster.lon.toFixed(6)}° E)`;
  
  const tierEl = document.getElementById("modal-tier");
  tierEl.innerText = cluster.severity_tier;
  tierEl.className = `tier-badge ${cluster.severity_tier}`;

  document.getElementById("modal-score").innerText = cluster.severity_score;
  document.getElementById("modal-passes").innerText = `${cluster.detection_count} passes`;
  document.getElementById("modal-budget").innerText = `$${cluster.repair_cost_est}`;
  document.getElementById("modal-date").innerText = `Work Order: ${cluster.work_order_id || 'PENDING'}`;

  const imgUrl = cluster.image_filename ? (cluster.image_filename.startsWith("sample_") ? `/data/samples/${cluster.image_filename}` : `/data/uploads/${cluster.image_filename}`) : "/data/samples/sample_pothole_d40_crit.jpg";
  document.getElementById("modal-img").src = imgUrl;

  document.getElementById("modal-dispatch-result").innerHTML = "";
  document.getElementById("defect-modal")?.classList.add("open");
};

function closeModal() {
  document.getElementById("defect-modal")?.classList.remove("open");
}

async function generateComplaintForCluster(clusterId) {
  const resultBox = document.getElementById("modal-dispatch-result");
  resultBox.innerHTML = `<span style="color:#38bdf8;">Generating Official Municipal PDF Grievance...</span>`;

  try {
    const res = await fetch(`/api/clusters/${clusterId}/complaint`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (res.ok) {
      resultBox.innerHTML = `
        <div style="background:rgba(16,185,129,0.15); border:1px solid #10b981; padding:0.6rem; border-radius:6px; color:#34d399;">
          <div>&#10003; Grievance <b>#${data.reference_no}</b> Dispatched!</div>
          <div style="margin-top:0.4rem;">
            <a href="${data.pdf_download_url}" target="_blank" class="btn-primary" style="display:inline-flex; padding:0.35rem 0.75rem; font-size:0.75rem;">
              Download Official PDF
            </a>
          </div>
        </div>
      `;
      loadStats();
      loadClusters();
      loadMunicipalityData();
    } else {
      resultBox.innerHTML = `<span style="color:#f43f5e;">Error: ${data.detail || 'Dispatch failed'}</span>`;
    }
  } catch (err) {
    resultBox.innerHTML = `<span style="color:#f43f5e;">Network Error generating grievance</span>`;
  }
}

// 7. Dashcam Studio Real-Time Simulation
function startLiveDriveSimulation() {
  const startBtn = document.getElementById("btn-start-simulation");
  const stopBtn = document.getElementById("btn-stop-simulation");
  const dot = document.getElementById("studio-stream-dot");
  const eventLog = document.getElementById("studio-event-log");
  const hudRoad = document.getElementById("hud-road");
  const hudGps = document.getElementById("hud-gps");
  const hudSpeed = document.getElementById("hud-speed");
  const dashcamImg = document.getElementById("dashcam-display");

  startBtn.style.display = "none";
  stopBtn.style.display = "inline-flex";
  dot.style.display = "inline-block";

  eventLog.innerHTML = `<div class="cluster-item" style="color:#38bdf8;">Connecting to live vehicle telemetry stream...</div>`;

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  liveSocket = new WebSocket(`${protocol}//${window.location.host}/ws/live-drive`);

  liveSocket.onopen = () => {
    eventLog.innerHTML += `<div class="cluster-item" style="color:#34d399;">&bull; Telemetry link established. Vehicle entering survey route.</div>`;
  };

  liveSocket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.status === "drive_complete") {
      stopLiveDriveSimulation();
      eventLog.innerHTML = `<div class="cluster-item" style="color:#34d399;">&#10003; Survey drive completed. All frames processed and deduplicated.</div>` + eventLog.innerHTML;
      return;
    }

    // Update HUD
    hudRoad.innerText = `SURVEY: ${data.road_name}`;
    hudGps.innerText = `${data.lat.toFixed(6)}, ${data.lon.toFixed(6)}`;
    hudSpeed.innerText = `SPEED: ${data.speed_kmh} km/h`;

    // Move Vehicle Marker on Map
    if (!activeVehicleMarker) {
      const carIcon = L.divIcon({
        html: `<div style="background:#38bdf8; width:18px; height:18px; border-radius:50%; border:3px solid #fff; box-shadow:0 0 15px #38bdf8;"></div>`,
        className: 'vehicle-pin',
        iconSize: [18, 18],
        iconAnchor: [9, 9]
      });
      activeVehicleMarker = L.marker([data.lat, data.lon], { icon: carIcon }).addTo(map);
    } else {
      activeVehicleMarker.setLatLng([data.lat, data.lon]);
    }

    // Check if defect detected in this second
    if (data.has_defect && data.defect) {
      const d = data.defect;
      dashcamImg.src = `/data/samples/${d.img}`;
      const logEntry = document.createElement("div");
      logEntry.className = "cluster-item";
      logEntry.innerHTML = `
        <div style="display:flex; justify-content:space-between; color:#f43f5e; font-weight:700;">
          <span>[DETECTION @ ${data.timestamp_sec}s] ${d.class}</span>
          <span>Sev: ${d.sev}</span>
        </div>
        <div style="color:var(--text-secondary);">${d.name} &bull; ${data.road_name}</div>
      `;
      eventLog.insertBefore(logEntry, eventLog.firstChild);
    }
  };

  liveSocket.onclose = () => {
    stopLiveDriveSimulation();
  };
}

function stopLiveDriveSimulation() {
  if (liveSocket) {
    liveSocket.close();
    liveSocket = null;
  }
  document.getElementById("btn-start-simulation").style.display = "inline-flex";
  document.getElementById("btn-stop-simulation").style.display = "none";
  document.getElementById("studio-stream-dot").style.display = "none";
}

// 8. Citizen Photo Upload Handling
function setupPhotoUpload() {
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("photo-input");
  const previewWrap = document.getElementById("upload-preview-wrap");
  const photoPreview = document.getElementById("photo-preview");
  const submitBtn = document.getElementById("btn-submit-report");
  const resultBox = document.getElementById("report-result-box");

  let selectedFile = null;

  dropZone?.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone?.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone?.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput?.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  function handleFileSelected(file) {
    selectedFile = file;
    const reader = new FileReader();
    reader.onload = (e) => {
      photoPreview.src = e.target.result;
      previewWrap.style.display = "block";
    };
    reader.readAsDataURL(file);
  }

  submitBtn?.addEventListener("click", async () => {
    if (!selectedFile) return;

    submitBtn.innerText = "Analyzing Road Surface via AI...";
    submitBtn.disabled = true;

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("lat", document.getElementById("report-lat").value);
    formData.append("lon", document.getElementById("report-lon").value);
    formData.append("road_name", document.getElementById("report-road").value);

    try {
      const res = await fetch("/api/detect/image", {
        method: "POST",
        body: formData
      });
      const data = await res.json();

      if (res.ok) {
        resultBox.style.display = "block";
        resultBox.innerHTML = `
          <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid #10b981; border-radius: var(--radius-md); padding: 1.25rem;">
            <h4 style="color: #34d399; font-weight: 800; margin-bottom: 0.5rem;">Defect Geotagged & Cataloged Successfully!</h4>
            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.75rem;">
              DBSCAN spatial deduplication merged your report with civic cluster records.
            </p>
            <div style="display:flex; gap:1rem; align-items:center; flex-wrap:wrap;">
              <img src="${data.annotated_image_url}" style="max-width:240px; border-radius:6px; border:1px solid #38bdf8;" />
              <div>
                <div><b>Severity:</b> ${data.detections[0]?.severity_score} / 100 (${data.detections[0]?.severity_tier})</div>
                <div><b>Coordinates:</b> ${data.gps.lat}, ${data.gps.lon}</div>
                <div><b>Corridor:</b> ${data.gps.road_name}</div>
              </div>
            </div>
          </div>
        `;
        loadStats();
        loadClusters();
        loadMunicipalityData();
      } else {
        resultBox.style.display = "block";
        resultBox.innerHTML = `<div style="color: #f43f5e;">Detection failed: ${data.detail}</div>`;
      }
    } catch (err) {
      resultBox.style.display = "block";
      resultBox.innerHTML = `<div style="color: #f43f5e;">Network error submitting photo</div>`;
    } finally {
      submitBtn.innerText = "Run AI Detection & Submit Grievance";
      submitBtn.disabled = false;
    }
  });
}

// 9. Municipality Hub Tables
async function loadMunicipalityData() {
  try {
    const res = await fetch("/api/municipality/roads");
    const roads = await res.json();
    const tbody = document.getElementById("worst-roads-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    roads.forEach(r => {
      const tr = document.createElement("tr");
      let barClass = "med";
      if (r.avg_severity >= 75) barClass = "crit";
      else if (r.avg_severity >= 50) barClass = "high";

      tr.innerHTML = `
        <td><b>${r.road_name}</b></td>
        <td>${r.defect_count} defects</td>
        <td>
          <div class="progress-bar-wrap">
            <div class="progress-bar-fill ${barClass}" style="width: ${Math.min(100, r.avg_severity)}%;"></div>
          </div>
          <span>${r.total_severity}</span>
        </td>
        <td><span class="tier-badge ${r.critical_count > 0 ? 'Critical' : 'Low'}">${r.critical_count} critical</span></td>
        <td>${r.pending_count} pending / ${r.repaired_count} repaired</td>
        <td><b>$${r.est_total_budget.toLocaleString()}</b></td>
        <td>
          <button class="btn-secondary" style="padding:0.35rem 0.7rem; font-size:0.75rem;" onclick="filterMapToRoad('${r.road_name}')">
            View on Map
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    // Populate Work Orders table
    const woTbody = document.getElementById("work-orders-tbody");
    if (woTbody) {
      woTbody.innerHTML = "";
      allClusters.slice(0, 15).forEach(c => {
        const wtr = document.createElement("tr");
        wtr.innerHTML = `
          <td>#${c.id}</td>
          <td><b>${c.damage_class}</b></td>
          <td>${c.road_name}</td>
          <td><span class="tier-badge ${c.severity_tier}">${c.severity_tier}</span></td>
          <td>
            <select class="filter-select" style="padding:0.3rem 0.5rem;" onchange="updateClusterStatus(${c.id}, this.value)">
              <option value="Reported" ${c.status === 'Reported' ? 'selected' : ''}>Reported</option>
              <option value="Under Review" ${c.status === 'Under Review' ? 'selected' : ''}>Under Review</option>
              <option value="Scheduled" ${c.status === 'Scheduled' ? 'selected' : ''}>Scheduled</option>
              <option value="Repaired" ${c.status === 'Repaired' ? 'selected' : ''}>Repaired</option>
            </select>
          </td>
          <td><code>${c.work_order_id || 'WO-PENDING'}</code></td>
          <td>
            <button class="btn-danger" style="padding:0.35rem 0.75rem; font-size:0.75rem;" onclick="generateComplaintForCluster(${c.id})">
              Generate PDF
            </button>
          </td>
        `;
        woTbody.appendChild(wtr);
      });
    }
  } catch (err) {
    console.error("Failed to load municipality data:", err);
  }
}

window.filterMapToRoad = function(roadName) {
  const mapTab = document.querySelector('[data-tab="tab-map"]');
  if (mapTab) mapTab.click();
  const searchInput = document.getElementById("search-road");
  if (searchInput) {
    searchInput.value = roadName;
    renderClusterMarkers();
  }
};

window.updateClusterStatus = async function(clusterId, newStatus) {
  try {
    await fetch(`/api/clusters/${clusterId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });
    loadStats();
    loadClusters();
  } catch (err) {
    console.error("Status update error:", err);
  }
};
