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
