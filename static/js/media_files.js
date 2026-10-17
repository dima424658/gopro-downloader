import { mediaPayload, requestJson, state } from "./core.js";
import { setStatus, updateSelectionControls } from "./ui.js";

export function setFileAction(button, downloaded) {
  button.replaceChildren();
  if (downloaded) {
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("viewBox", "0 0 24 24");
    icon.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute(
      "d",
      "M14 3h7v7M21 3 10 14M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6",
    );
    icon.append(path);
    button.append(icon);
  } else {
    const icon = document.createElement("span");
    icon.className = "ui-icon icon-download";
    icon.setAttribute("aria-hidden", "true");
    button.append(icon);
  }

  button.title = downloaded ? "Open file" : "Download original";
  button.setAttribute("aria-label", `${downloaded ? "Open" : "Download"} ${button.dataset.filename}`);
  button.dataset.downloaded = String(downloaded);

  const deleteButton = state.fileDeletes.get(button.dataset.filename);
  if (deleteButton) {
    const location = downloaded ? "local copy" : "camera";
    deleteButton.title = `Delete from ${location}`;
    deleteButton.setAttribute("aria-label", `Delete ${button.dataset.filename} from ${location}`);
  }
}

export async function openLocalFile(filename) {
  try {
    await requestJson("/api/local-media/open", {
      method: "POST",
      data: { ...mediaPayload(), filename },
      fallback: "Could not open the file.",
    });
    setStatus(`Opening ${filename}`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

export async function loadLocalFileStatuses(files) {
  try {
    const result = await requestJson("/api/local-media/status", {
      method: "POST",
      data: { ...mediaPayload(), filenames: files },
      fallback: "Could not check local files.",
    });
    for (const [filename, downloaded] of Object.entries(result.files || {})) {
      const button = state.fileActions.get(filename);
      if (button) setFileAction(button, downloaded);
      const checkbox = state.fileSelections.get(filename);
      if (checkbox) {
        checkbox.dataset.downloaded = String(downloaded);
        checkbox.dataset.statusPending = "false";
        checkbox.disabled = downloaded || state.busy;
        if (downloaded) checkbox.checked = false;
      }
    }
    updateSelectionControls();
  } catch (error) {
    for (const checkbox of state.fileSelections.values()) {
      checkbox.dataset.statusPending = "false";
      checkbox.disabled = state.busy;
    }
    updateSelectionControls();
    setStatus(error.message, "error");
  }
}

export function showDownloadedFile(filename) {
  const action = state.fileActions.get(filename);
  if (action) setFileAction(action, true);
  const checkbox = state.fileSelections.get(filename);
  if (checkbox) {
    checkbox.dataset.downloaded = "true";
    checkbox.dataset.statusPending = "false";
    checkbox.checked = false;
    checkbox.disabled = true;
  }
  updateSelectionControls();
}
