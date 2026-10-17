import { $, mediaPayload, state } from "./core.js";
import { createJobManager } from "./jobs.js";
import { createMediaView } from "./media.js";
import { showDownloadedFile } from "./media_files.js";
import { initializeTheme } from "./theme.js";
import { setStatus } from "./ui.js";

const config = JSON.parse($("app-config").textContent);
const MEDIA_REFRESH_INTERVAL_MS = 1_000;
const BATTERY_REFRESH_INTERVAL_MS = 60_000;
initializeTheme();

function setCameraBluetoothStatus(connected) {
  const indicator = $("camera-bluetooth-status");
  const label = connected ? "Camera reachable over Bluetooth" : "Camera unavailable over Bluetooth";
  indicator.classList.toggle("is-connected", connected);
  indicator.title = label;
  indicator.setAttribute("aria-label", label);
}

function setCameraWifiStatus(connected) {
  const indicator = $("camera-wifi-status");
  const label = connected ? "Camera connected over Wi-Fi" : "Camera is unavailable over Wi-Fi";
  indicator.classList.toggle("is-connected", connected);
  indicator.title = label;
  indicator.setAttribute("aria-label", label);
}

function setCameraBatteryStatus(percent) {
  const indicator = $("camera-battery-status");
  const value = Number.isInteger(percent) && percent >= 0 && percent <= 100 ? percent : null;
  const label = value === null ? "Camera battery level unavailable" : `Camera battery ${value}%`;
  indicator.classList.toggle("is-low", value !== null && value <= 20);
  indicator.classList.toggle("is-high", value !== null && value > 60);
  indicator.title = label;
  indicator.setAttribute("aria-label", label);
}

localStorage.removeItem("gopro-camera-bluetooth-status");
setCameraBluetoothStatus(false);

window.addEventListener("storage", (event) => {
  if (event.key === "gopro-camera-bluetooth-status") {
    setCameraBluetoothStatus(event.newValue === "connected");
  }
});

let jobs;
const media = createMediaView({
  startOperation: (...args) => jobs.start(...args),
  startThumbnailBatch: (...args) => jobs.startThumbnailBatch(...args),
});
jobs = createJobManager({
  showFiles: media.showFiles,
  onCameraWifiStatus: setCameraWifiStatus,
  onCameraMediaDeleted: () => window.refreshMedia(),
  onFilesDownloaded: (filenames) => filenames.forEach(showDownloadedFile),
});

$("settings").addEventListener("click", async () => {
  try {
    await window.pywebview.api.open_connection_window();
  } catch {
    setStatus("Could not open settings.", "error");
  }
});

window.addEventListener("storage", (event) => {
  if (event.key === "gopro-media-dir") {
    media.loadLocalFileStatuses([...state.fileActions.keys()]);
  }
});

localStorage.setItem("gopro-media-dir", config.media_dir);
localStorage.setItem("gopro-cohn-dir", config.cohn_dir);
window.refreshMedia = () =>
  jobs.start("/api/media", { ...mediaPayload(), command: "list-media" }, "Loading media list");
$("refresh").addEventListener("click", window.refreshMedia);
$("details-close").addEventListener("click", () => $("details-dialog").close());

let mediaRefreshVersion = 0;
async function checkMediaRefreshSignal() {
  try {
    const response = await fetch("/api/media/refresh-signal", {cache: "no-store"});
    if (!response.ok) return;
    const { version } = await response.json();
    if (version !== mediaRefreshVersion) {
      mediaRefreshVersion = version;
      window.refreshMedia();
    }
  } catch {
    // The local server may still be starting when this window loads.
  }
}

setInterval(checkMediaRefreshSignal, MEDIA_REFRESH_INTERVAL_MS);
checkMediaRefreshSignal();

let batteryRefreshTimer = null;
let batteryRefreshInFlight = false;

async function refreshBatteryStatus() {
  if (state.busy) {
    if (batteryRefreshTimer === null) {
      batteryRefreshTimer = setTimeout(() => {
        batteryRefreshTimer = null;
        refreshBatteryStatus();
      }, 1000);
    }
    return;
  }
  if (batteryRefreshInFlight) return;
  batteryRefreshInFlight = true;
  try {
    const response = await fetch("/api/camera/battery", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(mediaPayload()),
      cache: "no-store",
    });
    if (!response.ok) return;
    const { battery_percent: batteryPercent } = await response.json();
    setCameraBatteryStatus(batteryPercent);
  } catch {
    // Keep the last known charge if the camera is temporarily unreachable.
  } finally {
    batteryRefreshInFlight = false;
  }
}

if (config.auto_refresh) {
  window.refreshMedia();
  refreshBatteryStatus();
  setInterval(refreshBatteryStatus, BATTERY_REFRESH_INTERVAL_MS);
}
