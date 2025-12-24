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

// CLEAN URL - Remove default/empty parameters from URL
// Default values that should not appear in URL
const DEFAULT_PARAMS = {
    'view_mode': 'list',
    'sort': '-created_at',
};

// Remove empty and default parameters before HTMX sends the request
document.body.addEventListener('htmx:configRequest', function(event) {
    const params = event.detail.parameters;
    const toDelete = [];

    for (const key in params) {
        const value = params[key];
        // Remove empty values
        if (value === '' || value === null || value === undefined) {
            toDelete.push(key);
        }
        // Remove default values
        else if (DEFAULT_PARAMS[key] === value) {
            toDelete.push(key);
        }
    }

    toDelete.forEach(key => delete params[key]);
});

// FILTER BADGES

// Create a filter badge
function createFilterBadge(filterName, displayText, badgeClass = 'badge-secondary') {
    const container = document.getElementById('active-filters-badges');
    if (!container) return null;

    // Remove existing badge for this filter
    const existing = container.querySelector(`[data-filter="${filterName}"]`);
    if (existing) existing.remove();

    const badge = document.createElement('div');
    badge.className = `badge ${badgeClass} gap-1`;
    badge.dataset.filter = filterName;
    badge.innerHTML = `
        <span>${displayText}</span>
        <button type="button" class="hover:opacity-70 filter-badge-remove" data-filter="${filterName}">
            ✕
        </button>
    `;
    container.appendChild(badge);
    return badge;
}

// Remove a filter badge and reset the corresponding input
function removeFilterBadge(filterName) {
    const container = document.getElementById('active-filters-badges');
    if (!container) return;

    const badge = container.querySelector(`[data-filter="${filterName}"]`);
    if (badge) badge.remove();

    // Reset the corresponding input(s)
    if (filterName === 'review') {
        const reviewFrom = document.getElementById('review-from');
        const reviewTo = document.getElementById('review-to');
        if (reviewFrom) reviewFrom.value = '';
        if (reviewTo) reviewTo.value = '';
    } else if (filterName === 'contributor') {
        const input = document.getElementById('contributor');
        if (input) input.value = '';
    } else {
        const input = document.getElementById(filterName);
        if (input) input.value = '';
    }
}

// Handle filter badge remove button clicks
document.body.addEventListener('click', function(e) {
    const removeBtn = e.target.closest('.filter-badge-remove');
    if (!removeBtn) return;

    const filterName = removeBtn.dataset.filter;
    removeFilterBadge(filterName);

    // Trigger HTMX request to update the list
    const typeSelect = document.getElementById('type');
    if (typeSelect) {
        htmx.trigger(typeSelect, 'change');
    }
});

// Update badges when select filters change
document.body.addEventListener('change', function(e) {
    const target = e.target;
    const container = document.getElementById('active-filters-badges');
    if (!container) return;

    if (target.id === 'type' || target.id === 'status' || target.id === 'score') {
        const existing = container.querySelector(`[data-filter="${target.id}"]`);

        if (target.value) {
            // Get display text from selected option
            const selectedOption = target.options[target.selectedIndex];
            let displayText = selectedOption.textContent.trim();

            createFilterBadge(target.id, displayText);
        } else if (existing) {
            existing.remove();
        }
    }

    if (target.id === 'review-from' || target.id === 'review-to') {
        const reviewFrom = document.getElementById('review-from');
        const reviewTo = document.getElementById('review-to');
        const existing = container.querySelector('[data-filter="review"]');

        if (reviewFrom.value || reviewTo.value) {
            let displayText = '📅 ';
            if (reviewFrom.value && reviewTo.value) {
                displayText += `${reviewFrom.value} → ${reviewTo.value}`;
            } else if (reviewFrom.value) {
                displayText += `≥ ${reviewFrom.value}`;
            } else {
                displayText += `≤ ${reviewTo.value}`;
            }
            createFilterBadge('review', displayText);
        } else if (existing) {
            existing.remove();
        }
    }
});

// Handle contributor link clicks
document.body.addEventListener('click', function(e) {
    const link = e.target.closest('.contributor-link');
    if (!link) return;

    const contributorId = link.dataset.contributorId;
    const contributorName = link.dataset.contributorName;

    // Update hidden input
    document.getElementById('contributor').value = contributorId;

    // Create badge
    const badge = createFilterBadge('contributor', contributorName, 'badge-primary');
    if (badge) {
        badge.id = 'contributor-badge';
        const nameSpan = badge.querySelector('span');
        if (nameSpan) nameSpan.id = 'contributor-badge-name';
    }
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
