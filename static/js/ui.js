import { $, state } from "./core.js";

export function setStatus(message, kind = "") {
  $("status").textContent = message;
  $("status").className = kind;
}

export function setBusy(isBusy) {
  state.busy = isBusy;
  $("refresh").disabled = isBusy;
  document.querySelectorAll(".file-info, .file-action, .file-delete").forEach((button) => {
    button.disabled = isBusy;
  });
  document.querySelectorAll(".file-select, #select-all-files").forEach((checkbox) => {
    checkbox.disabled =
      isBusy || checkbox.dataset.downloaded === "true" || checkbox.dataset.statusPending === "true";
  });
  updateSelectionControls();
  $("cancel").hidden = !isBusy;
  $("cancel").disabled = !isBusy || !state.jobId;
}

export function updateSelectionControls() {
  const selectable = [...state.fileSelections.values()].filter((checkbox) => !checkbox.disabled);
  const selected = selectable.filter((checkbox) => checkbox.checked);
  const statusPending = [...state.fileSelections.values()].some((checkbox) => checkbox.dataset.statusPending === "true");
  const selectAll = $("select-all-files");
  const downloadSelected = $("download-selected");
  if (!selectAll || !downloadSelected) return;

  selectAll.checked = selectable.length > 0 && selected.length === selectable.length;
  selectAll.indeterminate = selected.length > 0 && selected.length < selectable.length;
  selectAll.disabled = state.busy || statusPending || selectable.length === 0;
  downloadSelected.disabled = state.busy || statusPending || selected.length === 0;
  downloadSelected.querySelector("span:last-child").textContent = selected.length
    ? `Download selected (${selected.length})`
    : "Download selected";
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;

  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(1)} ${units[unit]}`;
}

export function renderProgress(progress) {
  if (!progress) {
    $("progress").value = 0;
    $("progress-text").textContent = "Waiting";
    return;
  }
  if (progress.message) {
    if (Number.isInteger(progress.percent)) $("progress").value = progress.percent;
    const percent = Number.isInteger(progress.percent) ? `${progress.percent}% · ` : "";
    const speed = progress.bytes_per_second > 0 ? `${formatBytes(progress.bytes_per_second)}/s · ` : "";
    $("progress-text").textContent = `${percent}${speed}${progress.message}`;
    return;
  }

  if (Number.isInteger(progress.percent)) {
    $("progress").value = progress.percent;
  }
  const percent = Number.isInteger(progress.percent) ? `${progress.percent}%` : "";
  const transferred = progress.total
    ? `${formatBytes(progress.downloaded || 0)} / ${formatBytes(progress.total)}`
    : progress.downloaded
      ? `${formatBytes(progress.downloaded)} transferred`
      : "Preparing…";
  const speed = progress.bytes_per_second > 0 ? `${formatBytes(progress.bytes_per_second)}/s` : "";
  $("progress-text").textContent = [percent, transferred, speed].filter(Boolean).join(" · ");
}

export function showDetails(filename, rows) {
  $("details-title").textContent = filename;
  const list = $("details-list");
  list.replaceChildren();

  for (const row of rows || []) {
    const term = document.createElement("dt");
    term.textContent = row.label;
    const value = document.createElement("dd");
    value.textContent = row.value;
    list.append(term, value);
  }

  if (!rows || rows.length === 0) {
    const empty = document.createElement("dd");
    empty.textContent = "The camera returned no additional information.";
    list.append(empty);
  }
  $("details-dialog").showModal();
}
