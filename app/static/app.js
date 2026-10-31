const currentPath = window.location.pathname;

document.querySelectorAll("[data-nav-path]").forEach((link) => {
  const path = link.dataset.navPath;
  if (currentPath.startsWith(path) || (currentPath === "/" && path === "/portal")) {
    link.classList.add("active");
  }
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {
      // Hadithi remains usable when service workers are unavailable.
    });
  });
}
