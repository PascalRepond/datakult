// THEME SWITCHER
// Delegated, as the sidebar holding the theme radios is swapped by the filter form
document.addEventListener('change', (event) => {
    if (event.target.name !== 'theme-sidebar') return;
    const theme = event.target.value;
    if (theme === 'default') {
        localStorage.removeItem('theme');
        document.documentElement.removeAttribute('data-theme');
    } else {
        localStorage.setItem('theme', theme);
        document.documentElement.setAttribute('data-theme', theme);
    }
});

// Check the radio of the current theme (applied early by the inline script in the head)
function syncThemeRadios() {
    const currentTheme = localStorage.getItem('theme') || 'default';
    const currentRadio = document.querySelector(`input[name="theme-sidebar"][value="${currentTheme}"]`);
    if (currentRadio) {
        currentRadio.checked = true;
    }
}

// CLEAN URL - Remove default/empty parameters from URL
// Default values that should not appear in URL
const DEFAULT_PARAMS = {
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

// FILTER FORM
// Leave empty and default parameters out of its requests, and so of the URLs they push
document.body.addEventListener('htmx:configRequest', (event) => {
    if (event.detail.elt.id !== 'media-filters') return;
    const formData = event.detail.formData;
    const kept = [...formData.entries()].filter(([key, value]) => value !== '' && DEFAULT_PARAMS[key] !== value);
    [...new Set(formData.keys())].forEach((key) => formData.delete(key));
    kept.forEach(([key, value]) => formData.append(key, value));
});

// Close the sort dropdown once a sort is picked, by moving the focus out of it
document.body.addEventListener('change', (event) => {
    if (event.target.name === 'sort') event.target.blur();
});

// Remove a filter from its badge: clear its fields in the filter form, which then updates the list
document.body.addEventListener('click', (event) => {
    const btn = event.target.closest('.remove-filter-badge');
    const form = document.getElementById('media-filters');
    if (!btn || !form) return;

    const { filter, value } = btn.dataset;
    const names = filter === 'review' ? ['review_from', 'review_to'] : [filter];
    names.forEach((name) => {
        form.querySelectorAll(`[name="${name}"]`).forEach((field) => {
            if (value && field.value !== value) return;
            if (field.type === 'hidden') field.remove();
            else if (field.type === 'checkbox') field.checked = false;
            else if (field.type === 'radio') field.checked = field.value === '';
            else field.value = '';
        });
    });
    form.requestSubmit();
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

// INITIALIZE ALL FEATURES ON DOM READY
document.addEventListener('DOMContentLoaded', function() {
    syncThemeRadios();
    cleanUrlParameters();
    initToastMessages();
    registerServiceWorker();
});
document.body.addEventListener('htmx:afterSettle', syncThemeRadios);
