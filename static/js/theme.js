import { $, requestJson } from "./core.js";

function applyTheme(theme, persist = true) {
  const dark = theme === "dark";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  localStorage.setItem("gopro-theme", dark ? "dark" : "light");

  const toggle = $("theme-toggle");
  toggle.querySelector(".theme-icon").style.maskImage =
    `url('/static/icons/${dark ? "sun" : "moon"}.svg')`;
  toggle.title = dark ? "Switch to light theme" : "Switch to dark theme";
  toggle.setAttribute("aria-label", toggle.title);
  toggle.setAttribute("aria-pressed", String(dark));

  if (persist) {
    requestJson("/api/settings", {
      method: "POST",
      data: { theme: dark ? "dark" : "light" },
    }).catch(() => {});
  }
}

export function initializeTheme() {
  applyTheme(document.documentElement.dataset.theme, false);
  $("theme-toggle").addEventListener("click", () => {
    const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(theme);
  });

  window.addEventListener("storage", (event) => {
    if (event.key === "gopro-theme" && event.newValue) {
      applyTheme(event.newValue, false);
    }
  });
}
