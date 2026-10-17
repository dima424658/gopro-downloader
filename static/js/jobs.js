import { $, mediaPayload, requestJson, state } from "./core.js";
import { renderProgress, setBusy, setStatus, showDetails } from "./ui.js";
import { showDownloadedFile } from "./media_files.js";

function finishPolling() {
  clearInterval(state.timer);
  state.timer = null;
  state.jobId = null;
  setBusy(false);
}

export function createJobManager({ showFiles, onCameraWifiStatus, onCameraMediaDeleted, onFilesDownloaded }) {
  async function start(url, data, label) {
    if (state.busy) return;
    state.jobId = null;
    setBusy(true);
    renderProgress({ percent: 0 });
    setStatus(`${label}…`);

    try {
      const result = await requestJson(url, {
        method: "POST",
        data,
        fallback: "Could not start the operation.",
      });
      state.jobId = result.job_id;
      $("cancel").disabled = false;
      state.timer = setInterval(() => poll(result.job_id), 500);
    } catch (error) {
      setBusy(false);
      if (data.command === "list-media") onCameraWifiStatus(false);
      setStatus(error.message, "error");
    }
  }

  async function poll(jobId) {
    try {
      const job = await requestJson(`/api/jobs/${jobId}`);
      renderProgress(job.progress);
      if (job.command === "download-many" && job.progress?.completed_files?.length) {
        onFilesDownloaded(job.progress.completed_files);
      }
      if (!job.done) return;

      finishPolling();
      if (job.command === "list-media") {
        if (!job.cancelled) onCameraWifiStatus(!job.error);
      }
      if (job.cancelled) {
        setStatus("Operation cancelled.");
        return;
      }
      if (job.error) {
        setStatus(job.error, "error");
        return;
      }

      setStatus(`${job.label}: done`, "success");
      if (job.kind === "metadata") {
        showDetails(job.filename || state.selected, job.result);
      } else if (Array.isArray(job.result)) {
        showFiles(job.result);
      } else if (job.command === "download-many") {
        onFilesDownloaded(job.filenames || []);
        setStatus(`Downloaded ${job.filenames?.length || 0} files`, "success");
      } else if (job.command === "delete") {
        onCameraMediaDeleted();
      } else if (typeof job.result === "string") {
        setStatus(`Saved: ${job.result}`, "success");
        if (job.command === "download" && job.filename) showDownloadedFile(job.filename);
      } else if (job.result?.ip_address) {
        setStatus(`Camera configured: https://${job.result.ip_address}`, "success");
      }
    } catch (error) {
      finishPolling();
      setStatus(error.message, "error");
    }
  }

  async function startThumbnailBatch(files, applyUpdates, onComplete) {
    state.jobId = null;
    setBusy(true);
    setStatus("Media list ready; loading thumbnails in the background…");
    renderProgress({ percent: 0 });

    try {
      const result = await requestJson("/api/thumbnails", {
        method: "POST",
        data: { ...mediaPayload(), filenames: files },
        fallback: "Could not start loading thumbnails.",
      });
      state.jobId = result.job_id;
      $("cancel").disabled = false;
      state.timer = setInterval(async () => {
        try {
          const job = await requestJson(`/api/jobs/${result.job_id}`);
          applyUpdates(job.thumbnails);
          renderProgress(job.progress);
          if (!job.done) return;

          finishPolling();
          onComplete({ cancelled: job.cancelled, error: job.error });
        } catch (error) {
          finishPolling();
          setStatus(error.message, "error");
        }
      }, 350);
    } catch (error) {
      state.jobId = null;
      setBusy(false);
      setStatus(error.message, "error");
    }
  }

  async function cancel() {
    if (!state.jobId) return;
    $("cancel").disabled = true;
    setStatus("Cancelling…");
    try {
      await requestJson(`/api/jobs/${state.jobId}/cancel`, {
        method: "POST",
        fallback: "Could not cancel the operation.",
      });
      setStatus("Cancelling download…");
    } catch (error) {
      $("cancel").disabled = false;
      setStatus(error.message, "error");
    }
  }

  $("cancel").addEventListener("click", cancel);
  return { start, startThumbnailBatch };
}
