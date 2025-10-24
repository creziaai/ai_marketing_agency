// js/include.js
document.addEventListener("DOMContentLoaded", () => {
  const navbarContainer = document.getElementById("navbar");
  if (navbarContainer) {
    fetch("navbar.html")
      .then((response) => {
        if (!response.ok) throw new Error("Failed to load navbar");
        return response.text();
      })
      .then((html) => {
        navbarContainer.innerHTML = html;
      })
      .catch((err) => console.error(err));
  }
});
