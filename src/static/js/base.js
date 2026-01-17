// THEME SWITCHER
function initThemeSwitcher() {
    const htmlElement = document.documentElement;
    const themeRadios = document.querySelectorAll('input[name="theme-sidebar"]');

    const applyTheme = (theme) => {
        if (theme === "default") {
            localStorage.removeItem("theme");
            htmlElement.removeAttribute("data-theme");
        } else {
            localStorage.setItem("theme", theme);
            htmlElement.setAttribute("data-theme", theme);
        }
    };

    // Initialize theme
    const currentTheme = localStorage.getItem("theme") || "default";
    applyTheme(currentTheme);

    // Activate the radio button of the current theme
    const currentRadio = document.querySelector(`input[name="theme-sidebar"][value="${currentTheme}"]`);
    if (currentRadio) {
        currentRadio.checked = true;
    }

    // Add event listener to each radio button
    themeRadios.forEach((radio) => {
        radio.addEventListener("change", (event) => {
            const selectedTheme = event.target.value;
            applyTheme(selectedTheme);
        });
    });
}

// CLEAN URL - Remove default/empty parameters from URL
// Default values that should not appear in URL
const DEFAULT_PARAMS = {
    'view_mode': 'grid',
    'sort': '-review_date',
};

function cleanUrlParameters() {
    const url = new URL(window.location);
    const params = url.searchParams;
    let needsCleanup = false;

    // Build list of keys to delete (can't delete while iterating)
    const keysToDelete = [];

    for (const [key, value] of params.entries()) {
        // Remove empty values
        if (value === '' || value === null || value === undefined) {
            keysToDelete.push(key);
        }
        // Remove default values
        else if (DEFAULT_PARAMS[key] === value) {
            keysToDelete.push(key);
        }
    }

    // Delete marked keys
    keysToDelete.forEach(key => {
        params.delete(key);
        needsCleanup = true;
    });

    // Update URL if cleanup was needed
    if (needsCleanup) {
        const newUrl = url.pathname + (params.toString() ? '?' + params.toString() : '');
        window.history.replaceState({}, '', newUrl);
    }
}

// Handle badge removal - simple page reload with filter removed
document.body.addEventListener('click', function(e) {
    const btn = e.target.closest('.remove-filter-badge');
    if (!btn) return;
    e.preventDefault();

    const filterName = btn.dataset.filter;
    const filterValue = btn.dataset.value;

    // Build new URL without this filter value
    const url = new URL(window.location);
    const params = url.searchParams;

    if (filterValue) {
        // For multi-value filters (type, status, score)
        const values = params.getAll(filterName).filter(v => v !== filterValue);
        params.delete(filterName);
        values.forEach(v => params.append(filterName, v));
    } else if (filterName === 'review') {
        // Special case for review date filter - remove both from and to
        params.delete('review_from');
        params.delete('review_to');
    } else {
        // For single-value filters
        params.delete(filterName);
    }

    window.location.href = url.toString();
});

// FORM VALIDATION STYLING
// Toggle input-error class based on HTMX validation response
// (complements DaisyUI's validator class for server-side validation)
document.body.addEventListener('htmx:afterSwap', function(event) {
    const target = event.detail.target;

    // Check if target is an error label (id starts with 'error-')
    if (target && target.id && target.id.startsWith('error-')) {
        const fieldName = target.id.replace('error-', '');
        const input = document.getElementById('id_' + fieldName);

        if (input) {
            // Check if the response contains an error message
            const hasError = target.querySelector('.text-error') !== null;
            input.classList.toggle('input-error', hasError);
        }
    }
});

// TOAST MESSAGES
// Auto-dismiss toast messages after 5 seconds
function initToastMessages() {
    const toastContainer = document.querySelector('.toast');
    if (!toastContainer) return;

    const alerts = toastContainer.querySelectorAll('.alert');
    alerts.forEach((alert) => {
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alert.style.transition = 'opacity 0.3s ease-out';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
}

// SERVICE WORKER REGISTRATION
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/service-worker.js')
            .then((registration) => {
                console.log('Service Worker registered with scope:', registration.scope);
            })
            .catch((error) => {
                console.error('Service Worker registration failed:', error);
            });
    }
}

// MULTI-SELECT FILTER LABELS
// Update dropdown labels to show count of selected items
function initMultiSelectLabels() {
    const filters = [
        { name: 'type', labelId: 'type-filter-label' },
        { name: 'status', labelId: 'status-filter-label' },
        { name: 'score', labelId: 'score-filter-label' }
    ];

    filters.forEach(filter => {
        const label = document.getElementById(filter.labelId);
        if (!label) return;

        // Find the dropdown container
        const dropdown = label.closest('.dropdown');
        if (!dropdown) return;

        // Read localized strings from data attributes (with fallbacks)
        const defaultText = label.dataset.defaultText || 'All';
        const selectedText = label.dataset.selectedText || 'selected';

        const checkboxes = dropdown.querySelectorAll(`input[name="${filter.name}"]`);

        const updateLabel = () => {
            const checkedCount = dropdown.querySelectorAll(`input[name="${filter.name}"]:checked`).length;
            if (checkedCount === 0) {
                label.textContent = defaultText;
            } else {
                label.textContent = `${checkedCount} ${selectedText}`;
            }
        };

        // Add change listener to each checkbox
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', updateLabel);
        });
    });
}

// INITIALIZE ALL FEATURES ON DOM READY
document.addEventListener('DOMContentLoaded', function() {
    initThemeSwitcher();
    cleanUrlParameters();
    initToastMessages();
    registerServiceWorker();
    initMultiSelectLabels();
});
