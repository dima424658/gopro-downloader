const $ = (id) => document.getElementById(id);

export function enhanceSelect(id) {
  const select = $(id);
  const wrapper = document.createElement("div");
  wrapper.className = "app-dropdown";
  wrapper.id = `${id}-dropdown`;
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "dropdown-trigger";
  trigger.id = `${id}-trigger`;
  const label = document.querySelector(`label[for="${trigger.id}"]`);
  if (label) trigger.setAttribute("aria-label", label.textContent.trim());
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("aria-controls", `${id}-options`);
  const value = document.createElement("span");
  value.className = "dropdown-value";
  trigger.append(value);
  const menu = document.createElement("div");
  menu.className = "dropdown-menu";
  menu.id = `${id}-options`;
  menu.setAttribute("role", "listbox");
  menu.hidden = true;
  select.parentNode.insertBefore(wrapper, select);
  wrapper.append(trigger, menu, select);
  select.classList.add("native-select-control");
  select.tabIndex = -1;
  select.setAttribute("aria-hidden", "true");

  function closeMenu(focusTrigger = false) {
    menu.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    if (focusTrigger) trigger.focus();
  }

  function render() {
    wrapper.hidden = select.hidden;
    trigger.disabled = select.disabled;
    if (wrapper.hidden || trigger.disabled) closeMenu();
    menu.replaceChildren();
    for (const [index, option] of Array.from(select.options).entries()) {
      const item = document.createElement("div");
      item.className = "dropdown-option";
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", String(option.selected));
      item.tabIndex = -1;
      item.dataset.index = String(index);
      item.textContent = option.textContent;
      item.addEventListener("click", () => {
        select.value = option.value;
        select.dispatchEvent(new Event("change", {bubbles: true}));
        closeMenu(true);
      });
      menu.append(item);
    }
    const selected = select.selectedOptions[0];
    value.textContent = selected ? selected.textContent : "Select…";
  }

  function openMenu(focusLast = false) {
    if (trigger.disabled || wrapper.hidden) return;
    menu.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    const options = [...menu.querySelectorAll('[role="option"]')];
    const active = options.find((item) => item.getAttribute("aria-selected") === "true") || options[0];
    (focusLast ? options.at(-1) : active)?.focus();
  }

  trigger.addEventListener("click", () => menu.hidden ? openMenu() : closeMenu());
  trigger.addEventListener("keydown", (event) => {
    if (["ArrowDown", "Enter", " "].includes(event.key)) {
      event.preventDefault();
      openMenu();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      openMenu(true);
    }
  });
  menu.addEventListener("keydown", (event) => {
    const options = [...menu.querySelectorAll('[role="option"]')];
    const index = options.indexOf(document.activeElement);
    if (event.key === "Escape") {
      event.preventDefault();
      closeMenu(true);
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      options[Math.max(0, Math.min(options.length - 1, index + (event.key === "ArrowDown" ? 1 : -1)))]?.focus();
    } else if (["Enter", " "].includes(event.key)) {
      event.preventDefault();
      document.activeElement?.click();
    }
  });
  document.addEventListener("click", (event) => {
    if (!wrapper.contains(event.target)) closeMenu();
  });
  select.addEventListener("change", render);
  new MutationObserver(render).observe(select, {childList: true, subtree: true, attributes: true, attributeFilter: ["hidden", "disabled", "selected"]});
  render();
}
