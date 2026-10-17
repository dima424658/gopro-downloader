import { $, mediaPayload, requestJson, state } from "./core.js";
import { setStatus, updateSelectionControls } from "./ui.js";
import { loadLocalFileStatuses, openLocalFile, setFileAction } from "./media_files.js";

function applyThumbnailUpdates(thumbnails) {
  for (const [filename, item] of Object.entries(thumbnails || {})) {
    const preview = state.previews.get(filename);
    if (!preview || item.status === "pending") continue;

    if (item.status === "ready") {
      const image = document.createElement("img");
      image.alt = `Thumbnail for ${filename}`;
      image.loading = "lazy";
      image.src = item.url;
      preview.replaceChildren(image);
    } else {
      preview.textContent = "No thumbnail";
      preview.title = item.error || "Thumbnail unavailable";
    }
  }
}

function finishThumbnailBatch({ cancelled, error }) {
  if (cancelled) {
    for (const preview of state.previews.values()) {
      if (preview.textContent === "Loading…") preview.textContent = "Cancelled";
    }
    setStatus("Thumbnail loading cancelled.");
  } else if (error) {
    for (const preview of state.previews.values()) {
      if (preview.textContent === "Loading…") preview.textContent = "No thumbnail";
    }
    setStatus(`Could not load thumbnails: ${error}`, "error");
  } else {
    setStatus("Media list and thumbnails are ready", "success");
  }
}

export function createMediaView({ startOperation, startThumbnailBatch }) {
  let pendingDelete = null;

  function activateFile(name, fileAction) {
    if (state.busy) return;

    if (fileAction.dataset.downloaded === "true") {
      openLocalFile(name);
      return;
    }

    startOperation(
      "/api/media",
      { ...mediaPayload(), command: "download", filename: name },
      "Downloading original",
    );
  }

  function showFiles(files) {
    const body = $("files");
    body.replaceChildren();
    state.selected = null;
    state.previews.clear();
    state.fileActions.clear();
    state.fileDeletes.clear();
    state.fileSelections.clear();

    if (files.length === 0) {
      const row = body.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 1;
      cell.className = "empty";
      cell.textContent = "There are no files on the camera.";
    } else {
      files.forEach((name) => {
        const row = body.insertRow();
        const cell = row.insertCell();
        const entry = document.createElement("div");
        entry.className = "media-entry";

        const selection = document.createElement("input");
        selection.type = "checkbox";
        selection.className = "file-select";
        selection.disabled = true;
        selection.dataset.statusPending = "true";
        selection.setAttribute("aria-label", `Select ${name} for download`);
        selection.addEventListener("click", (event) => event.stopPropagation());
        selection.addEventListener("change", updateSelectionControls);

        const preview = document.createElement("div");
        preview.className = "preview";
        preview.textContent = "Loading…";

        const filename = document.createElement("span");
        filename.className = "filename";
        filename.textContent = name;

        const info = document.createElement("button");
        info.className = "file-info secondary";
        info.textContent = "i";
        info.title = "File information";
        info.setAttribute("aria-label", `File information ${name}`);
        info.disabled = state.busy;
        info.addEventListener("click", (event) => {
          event.stopPropagation();
          startOperation(
            "/api/media/metadata",
            { ...mediaPayload(), filename: name },
            "Loading file information",
          );
        });

        const fileAction = document.createElement("button");
        fileAction.className = "file-action secondary";
        fileAction.dataset.filename = name;
        fileAction.disabled = state.busy;
        setFileAction(fileAction, false);
        fileAction.addEventListener("click", (event) => {
          event.stopPropagation();
          activateFile(name, fileAction);
        });

        const deleteButton = document.createElement("button");
        deleteButton.className = "file-delete secondary";
        deleteButton.type = "button";
        deleteButton.dataset.filename = name;
        deleteButton.disabled = state.busy;
        const deleteIcon = document.createElement("span");
        deleteIcon.className = "ui-icon icon-trash";
        deleteIcon.setAttribute("aria-hidden", "true");
        deleteButton.append(deleteIcon);
        deleteButton.addEventListener("click", async (event) => {
          event.stopPropagation();
          if (state.busy) return;
          deleteButton.disabled = true;
          try {
            const result = await requestJson("/api/local-media/status", {
              method: "POST",
              data: { ...mediaPayload(), filenames: [name] },
              fallback: "Could not check for a local copy.",
            });
            if (state.busy || state.fileActions.get(name) !== fileAction) return;
            const local = result.files?.[name] === true;
            setFileAction(fileAction, local);
            pendingDelete = { filename: name, local };
            $("delete-title").textContent = local ? "Delete local copy?" : "Delete from camera?";
            $("delete-message").textContent = local
              ? `“${name}” will be permanently deleted from this computer. The original on the camera will remain.`
              : `“${name}” will be permanently deleted from the camera’s memory card. This cannot be undone.`;
            $("delete-dialog").showModal();
          } catch (error) {
            setStatus(error.message, "error");
          } finally {
            deleteButton.disabled = state.busy;
          }
        });

        entry.append(selection, preview, filename, info, fileAction, deleteButton);
        cell.append(entry);
        state.previews.set(name, preview);
        state.fileActions.set(name, fileAction);
        state.fileDeletes.set(name, deleteButton);
        state.fileSelections.set(name, selection);
        setFileAction(fileAction, false);
        row.addEventListener("click", () => {
          body.querySelectorAll("tr").forEach((item) => item.classList.remove("selected"));
          row.classList.add("selected");
          state.selected = name;
        });
        row.addEventListener("dblclick", (event) => {
          if (event.target instanceof Element && event.target.closest("button, input")) return;
          activateFile(name, fileAction);
        });
      });
    }

    updateSelectionControls();

    if (files.length > 0) {
      startThumbnailBatch(files, applyThumbnailUpdates, finishThumbnailBatch);
      loadLocalFileStatuses(files);
    }
  }

  $("select-all-files").addEventListener("change", (event) => {
    const checked = event.currentTarget.checked;
    for (const checkbox of state.fileSelections.values()) {
      if (!checkbox.disabled) checkbox.checked = checked;
    }
    updateSelectionControls();
  });

  $("download-selected").addEventListener("click", () => {
    const filenames = [...state.fileSelections]
      .filter(([, checkbox]) => checkbox.checked && !checkbox.disabled)
      .map(([filename]) => filename);
    if (!filenames.length) return;
    startOperation(
      "/api/media",
      { ...mediaPayload(), command: "download-many", filenames },
      "Downloading selected files",
    );
  });

  $("delete-cancel").addEventListener("click", () => {
    $("delete-dialog").close();
  });
  $("delete-dialog").addEventListener("close", () => {
    pendingDelete = null;
  });
  $("delete-confirm").addEventListener("click", async () => {
    if (!pendingDelete || state.busy) return;
    const target = pendingDelete;
    pendingDelete = null;
    $("delete-dialog").close();

    if (!target.local) {
      startOperation(
        "/api/media",
        { ...mediaPayload(), command: "delete", filename: target.filename },
        "Deleting from camera",
      );
      return;
    }

    try {
      await requestJson("/api/local-media/delete", {
        method: "POST",
        data: { ...mediaPayload(), filename: target.filename },
        fallback: "Could not delete local file.",
      });
      const action = state.fileActions.get(target.filename);
      if (action) setFileAction(action, false);
      const checkbox = state.fileSelections.get(target.filename);
      if (checkbox) {
        checkbox.dataset.downloaded = "false";
        checkbox.dataset.statusPending = "false";
        checkbox.disabled = state.busy;
      }
      updateSelectionControls();
      setStatus(`Deleted local copy of ${target.filename}`, "success");
    } catch (error) {
      setStatus(error.message, "error");
    }
  });

  return { showFiles, loadLocalFileStatuses };
}
