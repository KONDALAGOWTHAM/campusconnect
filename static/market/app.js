const themeButton = document.querySelector(".theme-toggle");
const pageTheme = document.documentElement.dataset;
themeButton?.setAttribute("aria-pressed", String(pageTheme.theme === "dark"));

themeButton?.addEventListener("click", () => {
  pageTheme.theme = pageTheme.theme === "dark" ? "light" : "dark";
  themeButton.setAttribute("aria-pressed", String(pageTheme.theme === "dark"));
  try { localStorage.setItem("campus-theme", pageTheme.theme); } catch {}
});

document.addEventListener("click", (event) => {
  event.target.closest(".dismiss")?.closest(".toast")?.remove();
  const confirmation = event.target.closest("[data-confirm]");
  if (confirmation && !window.confirm(confirmation.dataset.confirm)) event.preventDefault();

  const thumbnail = event.target.closest("[data-gallery-src]");
  if (thumbnail) {
    document.querySelector("[data-main-photo]").src = thumbnail.dataset.gallerySrc;
    document.querySelectorAll("[data-gallery-src]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button === thumbnail));
    });
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.querySelectorAll("header details[open]").forEach((menu) => {
      if (menu.contains(document.activeElement) || menu.matches(".navigation-menu")) {
        menu.open = false;
        menu.querySelector("summary")?.focus();
      }
    });
  }
});

const photoInput = document.querySelector("[data-photos]");
const dropzone = document.querySelector("[data-dropzone]");
const previews = document.querySelector("[data-previews]");

photoInput?.addEventListener("change", () => {
  previews.replaceChildren();
  for (const file of Array.from(photoInput.files).slice(0, 5)) {
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) continue;
    const image = document.createElement("img");
    const url = URL.createObjectURL(file);
    image.src = url;
    image.alt = file.name;
    image.addEventListener("load", () => URL.revokeObjectURL(url), {once:true});
    image.addEventListener("error", () => URL.revokeObjectURL(url), {once:true});
    previews.append(image);
  }
});

dropzone?.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropzone.classList.add("dragging");
});
dropzone?.addEventListener("dragleave", () => dropzone.classList.remove("dragging"));
dropzone?.addEventListener("drop", (event) => {
  event.preventDefault();
  dropzone.classList.remove("dragging");
  photoInput.files = event.dataTransfer.files;
  photoInput.dispatchEvent(new Event("change"));
});

const historyPanel = document.querySelector("[data-messages]");
if (historyPanel) {
  historyPanel.scrollTop = historyPanel.scrollHeight;
  let previous;
  async function refreshMessages() {
    try {
      if (!document.hidden) {
        const response = await fetch(historyPanel.dataset.messages, {redirect:"manual"});
        if (response.ok) {
          const html = await response.text();
          if (html !== previous) {
            const atBottom = historyPanel.scrollHeight - historyPanel.scrollTop - historyPanel.clientHeight < 28;
            historyPanel.innerHTML = html;
            if (atBottom) historyPanel.scrollTop = historyPanel.scrollHeight;
            previous = html;
          }
        }
      }
    } catch {
      // Retain the current conversation during a temporary connection failure.
    } finally {
      window.setTimeout(refreshMessages, 6500);
    }
  }
  window.setTimeout(refreshMessages, 6500);
}
