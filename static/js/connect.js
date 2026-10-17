import { enhanceSelect } from "./dropdown.js";
import { requestJson } from "./api.js";

const config = JSON.parse(document.getElementById("connect-config").textContent);
const $ = (id) => document.getElementById(id);
let selectedTarget = "";
const MANUAL_WIFI_VALUE = "__manual_wifi__";

enhanceSelect("device");
enhanceSelect("wifi-network");

const savedMediaDir = localStorage.getItem("gopro-media-dir");
$("media-dir").value = savedMediaDir && savedMediaDir !== "media" ? savedMediaDir : config.media_dir;
localStorage.setItem("gopro-media-dir", $("media-dir").value);
$("output-dir").value = config.cohn_dir;
$("ssid").value = config.wifi_ssid || "";

async function saveCohnDirectory() {
  const cohnDir = $("output-dir").value.trim();
  $("output-dir").value = cohnDir;
  await requestJson("/api/settings", {
    method: "POST",
    data: {cohn_dir: cohnDir},
    fallback: "Could not save the configuration folder.",
  });
  localStorage.setItem("gopro-cohn-dir", cohnDir);
}

$("media-dir").addEventListener("change", async () => {
  const mediaDir = $("media-dir").value.trim() || config.media_dir;
  $("media-dir").value = mediaDir;
  localStorage.setItem("gopro-media-dir", mediaDir);
  try {
    await requestJson("/api/settings", {
      method: "POST",
      data: {media_dir: mediaDir},
      fallback: "Could not save the download folder.",
    });
  } catch (error) { setStatus(error.message, "error"); }
});
$("output-dir").addEventListener("change", async () => {
  try { await saveCohnDirectory(); } catch (error) { setStatus(error.message, "error"); }
});

$("choose-dir").addEventListener("click", async () => {
  try {
    const directory = await window.pywebview.api.choose_download_directory($("media-dir").value.trim());
    if (!directory) return;
    $("media-dir").value = directory;
    $("media-dir").dispatchEvent(new Event("change"));
  } catch (_) { setStatus("Could not open the folder picker.", "error"); }
});
$("choose-config-dir").addEventListener("click", async () => {
  try {
    const directory = await window.pywebview.api.choose_config_directory($("output-dir").value.trim());
    if (!directory) return;
    $("output-dir").value = directory;
    await saveCohnDirectory();
    setStatus("Configuration folder saved.", "success");
  } catch (_) { setStatus("Could not open the configuration folder picker.", "error"); }
});

window.addEventListener("storage", (event) => {
  if (event.key === "gopro-theme" && event.newValue) document.documentElement.dataset.theme = event.newValue;
});

$("pairing-help-open").addEventListener("click", () => $("pairing-help-dialog").showModal());
$("pairing-help-close").addEventListener("click", () => $("pairing-help-dialog").close());

function setStatus(text, kind = "") {
  const status = $("status");
  const wifiActive = !$("wifi-step").hidden;
  const step = $(wifiActive ? "wifi-step" : "device-step");
  if (wifiActive) {
    const heading = step.querySelector("h3");
    step.insertBefore(status, heading.nextElementSibling);
  } else {
    step.insertBefore(status, step.firstChild);
  }
  status.textContent = text;
  status.className = kind;
  status.hidden = !text;
}

function chosenTarget() {
  return $("device").hidden ? $("target").value.trim() : $("device").value;
}

async function waitForJob(jobId, onProgress = () => {}) {
  while (true) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    const job = await requestJson(`/api/jobs/${jobId}`);
    if (job.error) throw new Error(job.error);
    onProgress(job);
    if (!job.done) continue;
    if (job.cancelled) throw new Error("Operation cancelled.");
    return job.result;
  }
}

async function startJob(endpoint, payload, label) {
  const result = await requestJson(endpoint, {
    method: "POST",
    data: payload,
    fallback: "Could not start the operation.",
  });
  setStatus(label);
  return waitForJob(result.job_id);
}

function updateManualSsidVisibility() {
  const manualSelected = $("wifi-network").value === MANUAL_WIFI_VALUE;
  $("manual-ssid-group").hidden = !manualSelected;
  $("ssid").disabled = !manualSelected || $("wifi-network").disabled;
}

async function scanWifiNetworks() {
  const scanButton = $("scan-wifi");
  const select = $("wifi-network");
  const actionButtons = [$("submit"), $("skip-wifi")];
  scanButton.disabled = true;
  select.disabled = true;
  $("ssid").disabled = true;
  $("password").disabled = true;
  actionButtons.forEach((button) => { button.disabled = true; });
  $("wifi-scan-status").textContent = "Scanning for Wi-Fi networks…";
  select.replaceChildren(new Option("Select a network", ""));
  updateManualSsidVisibility();
  try {
    const networks = await startJob(
      "/api/wifi/scan",
      {target: selectedTarget, output_dir: $("output-dir").value.trim()},
      "",
    );
    for (const ssid of networks) select.add(new Option(ssid, ssid));
    select.add(new Option("Enter SSID manually…", MANUAL_WIFI_VALUE));
    $("wifi-scan-status").textContent = networks.length ? "" : "No networks found. You can enter the SSID manually.";
    if (!networks.length) setStatus("Enter the SSID manually.", "error");
    else setStatus("");
  } catch (error) {
    select.add(new Option("Enter SSID manually…", MANUAL_WIFI_VALUE));
    $("wifi-scan-status").textContent = "Could not find networks. You can enter the SSID manually.";
    setStatus(error.message, "error");
  } finally {
    select.disabled = false;
    updateManualSsidVisibility();
    $("password").disabled = false;
    scanButton.disabled = false;
    actionButtons.forEach((button) => { button.disabled = false; });
  }
}

$("wifi-network").addEventListener("change", updateManualSsidVisibility);

async function scanDevices() {
  const button = $("rescan");
  const select = $("device");
  const hadDevices = select.options.length > 0;
  button.disabled = true;
  $("scan-status").textContent = "Searching for nearby GoPro cameras over Bluetooth…";
  if (!hadDevices) select.add(new Option("Searching for cameras…", ""));
  select.hidden = false;
  select.disabled = true;
  $("device-label").hidden = false;
  $("manual-device").hidden = true;
  $("connect-ble").disabled = true;
  try {
    const devices = await startJob("/api/ble/scan", {}, "");
    select.replaceChildren();
    if (devices.length) {
      for (const device of devices) {
        const option = document.createElement("option");
        option.value = device.target;
        option.textContent = `${device.name} (${device.target})`;
        select.append(option);
      }
      $("scan-status").textContent = "";
      $("connect-ble").disabled = false;
    } else {
      select.hidden = true;
      $("device-label").hidden = true;
      $("manual-device").hidden = false;
      $("scan-status").textContent = "No cameras found.";
      $("target").focus();
    }
    setStatus("");
  } catch (error) {
    if (!hadDevices) {
      select.replaceChildren();
      select.hidden = true;
      $("device-label").hidden = true;
      $("manual-device").hidden = false;
    }
    $("connect-ble").disabled = !select.value;
    $("scan-status").textContent = "Automatic discovery did not complete.";
    setStatus(error.message, "error");
  } finally {
    select.disabled = false;
    button.disabled = false;
  }
}

$("device").addEventListener("change", () => { $("connect-ble").disabled = !$("device").value; });
$("target").addEventListener("input", () => {
  $("connect-ble").disabled = !/^[A-Za-z0-9]{4}$/.test($("target").value.trim());
});
$("rescan").addEventListener("click", scanDevices);

$("connect-ble").addEventListener("click", async () => {
  const target = chosenTarget();
  if (!target) return;
  $("connect-ble").disabled = true;
  $("connect-ble").textContent = "Connecting…";
  $("rescan").disabled = true;
  setStatus(`Connecting to GoPro ${target} over Bluetooth…`);
  localStorage.setItem("gopro-camera-bluetooth-status", "disconnected");
  try {
    selectedTarget = await startJob(
      "/api/ble/connect",
      {target, output_dir: $("output-dir").value.trim()},
      "Connecting to the camera over Bluetooth…",
    );
    $("connected-device").hidden = false;
    $("connected-device").textContent = `Bluetooth connected: GoPro ${selectedTarget}.`;
    localStorage.setItem("gopro-camera-bluetooth-status", "connected");
    $("pairing-help-open").hidden = true;
    $("wifi-step").hidden = false;
    $("device-step").hidden = true;
    await scanWifiNetworks();
  } catch (error) {
    localStorage.setItem("gopro-camera-bluetooth-status", "disconnected");
    setStatus(error.message, "error");
    $("connect-ble").disabled = false;
    $("connect-ble").textContent = "Connect over Bluetooth";
    $("rescan").disabled = false;
  }
});

$("scan-wifi").addEventListener("click", scanWifiNetworks);

async function configureCamera(skipWifi = false) {
  const selectedNetwork = $("wifi-network").value;
  const ssid = skipWifi ? "" : selectedNetwork === MANUAL_WIFI_VALUE ? $("ssid").value.trim() : selectedNetwork;
  if (!skipWifi && !ssid) {
    setStatus("Select a Wi-Fi network or choose “Enter SSID manually”.", "error");
    return;
  }
  const buttons = [$("submit"), $("skip-wifi")];
  buttons.forEach((button) => { button.disabled = true; });
  const payload = {
    target: selectedTarget,
    ssid,
    wifi_password: skipWifi ? "" : $("password").value,
    output_dir: $("output-dir").value.trim(),
  };
  $("password").value = "";
  try {
    const details = await startJob("/api/provision", payload, "Setting up Wi-Fi and HTTPS access…");
    const successMessage = `COHN is configured.\nCamera: https://${details.ip_address || ""}\nCertificate: ${details.certificate || ""}`;
    setStatus(successMessage, "success");
    try {
      const response = await fetch("/api/media/refresh-signal", {method: "POST"});
      if (!response.ok) throw new Error("Could not request a media list refresh.");
    } catch (_) {
      setStatus(`${successMessage}\nCould not start refreshing the media list.`, "error");
    }
    setTimeout(() => window.pywebview.api.close_connection_window(), 1800);
  } catch (error) {
    setStatus(error.message, "error");
    buttons.forEach((button) => { button.disabled = false; });
  }
}

$("submit").addEventListener("click", () => configureCamera());
$("skip-wifi").addEventListener("click", () => configureCamera(true));
scanDevices();
