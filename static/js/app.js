const menuButton = document.getElementById("menuButton");
const sidebar = document.getElementById("sidebar");
const mobileBackdrop = document.getElementById("mobileBackdrop");
const userDropdownToggle = document.getElementById("userDropdownToggle");
const userDropdown = document.getElementById("userDropdown");

function setMobileMenu(open) {
  if (!sidebar) return;
  sidebar.classList.toggle("open", open);
  mobileBackdrop?.classList.toggle("show", open);
  document.body.classList.toggle("menu-open", open);
  menuButton?.setAttribute("aria-expanded", String(open));
}

menuButton?.addEventListener("click", () => {
  setMobileMenu(!sidebar.classList.contains("open"));
});

mobileBackdrop?.addEventListener("click", () => setMobileMenu(false));

document.querySelectorAll(".sidebar a").forEach(link => {
  link.addEventListener("click", () => setMobileMenu(false));
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape" && sidebar?.classList.contains("open")) {
    setMobileMenu(false);
  }
});

userDropdownToggle?.addEventListener("click", (e) => {
  e.stopPropagation();
  userDropdown?.classList.toggle("open");
});

document.addEventListener("click", (e) => {
  if (userDropdown && !userDropdown.contains(e.target) && !userDropdownToggle.contains(e.target)) {
    userDropdown.classList.remove("open");
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    userDropdown?.classList.remove("open");
  }
});
