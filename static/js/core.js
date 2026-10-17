export { requestJson } from "./api.js";

export const state = {
  selected: null,
  busy: false,
  timer: null,
  jobId: null,
  previews: new Map(),
  fileActions: new Map(),
  fileDeletes: new Map(),
  fileSelections: new Map(),
};

const appConfig = JSON.parse(document.getElementById("app-config").textContent);

export const $ = (id) => document.getElementById(id);

export function mediaPayload() {
  return {
    output_dir: localStorage.getItem("gopro-cohn-dir") || appConfig.cohn_dir,
    media_dir: localStorage.getItem("gopro-media-dir") || appConfig.media_dir,
  };
}
