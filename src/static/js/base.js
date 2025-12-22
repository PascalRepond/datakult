// THEME SWITCHER
document.addEventListener("DOMContentLoaded", () => {
    const htmlElement = document.documentElement;
    const themeRadios = document.querySelectorAll('input[name="theme-dropdown"]');

    const applyTheme = (theme) => {
        if (theme === "default") {
            localStorage.removeItem("theme");
        } else {
            localStorage.setItem("theme", theme);
            htmlElement.setAttribute("value", theme);
        }
    };

    // initialise theme
    const currentTheme = localStorage.getItem("theme") || "default";
    applyTheme(currentTheme);

    // activate the menu item of the current theme
    const currentRadio = document.querySelector(`input[value="${currentTheme}"]`);
    if (currentRadio) {
        currentRadio.checked = true;
    }

    // add an event listener to each menu item
    themeRadios.forEach((radio) => {
        radio.addEventListener("change", (event) => {
        const selectedTheme = event.target.value;
        applyTheme(selectedTheme);
        });
    });
});

// VIEW MODE TOGGLE
// Dynamically update active button state on click
const viewModeToggle = document.getElementById('view-mode');
if (viewModeToggle) {
    viewModeToggle.addEventListener('click', function(e) {
        if (e.target.closest('button')) {
            document.querySelectorAll('#view-mode button').forEach(btn => btn.classList.remove('btn-active'));
            e.target.closest('button').classList.add('btn-active');
        }
    });
}
