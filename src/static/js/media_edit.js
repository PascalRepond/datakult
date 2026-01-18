// Interactivity for media edit page: chips (contributors, tags) and date picker

document.addEventListener('DOMContentLoaded', () => {
  // Set up "Set to today" button for review date
  const setTodayBtn = document.getElementById('set-today-btn');
  const reviewDateInput = document.getElementById('id_review_date');

  if (setTodayBtn && reviewDateInput) {
    setTodayBtn.addEventListener('click', () => {
      reviewDateInput.value = new Date().toISOString().split('T')[0];
    });
  }

  // Handle cover file input to clear TMDB poster when a file is selected
  const coverInput = document.getElementById('id_cover');
  const tmdbPosterUrlInput = document.getElementById('tmdb-poster-url-input');
  const tmdbPosterPreview = document.getElementById('tmdb-poster-preview');

  if (coverInput) {
    coverInput.addEventListener('change', () => {
      if (coverInput.files && coverInput.files.length > 0) {
        // Clear the TMDB poster URL so the uploaded file takes precedence
        if (tmdbPosterUrlInput) {
          tmdbPosterUrlInput.value = '';
        }
        // Update preview to show the selected file instead
        if (tmdbPosterPreview) {
          const file = coverInput.files[0];
          const reader = new FileReader();
          reader.onload = (e) => {
            tmdbPosterPreview.src = e.target.result;
            tmdbPosterPreview.alt = file.name;
          };
          reader.readAsDataURL(file);
        }
      }
    });
  }

  // Store all chip inputs for HTMX event handling
  const chipInputs = [];

  // Generic chip input handler with optional HTMX autocomplete support
  const initChipInput = ({ inputId, containerId, suggestionsId, hiddenInputName, badgeClass }) => {
    const input = document.getElementById(inputId);
    const container = document.getElementById(containerId);
    const suggestions = suggestionsId ? document.getElementById(suggestionsId) : null;
    if (!input || !container) return null;

    const chipExists = (name) => {
      const lower = name.trim().toLowerCase();
      return Array.from(container.querySelectorAll('.badge')).some((badge) => {
        const badgeName =
          badge.dataset.name || badge.querySelector('span')?.textContent || badge.textContent;
        return (badgeName || '').trim().toLowerCase() === lower;
      });
    };

    const addChip = (name) => {
      if (!name || chipExists(name)) return;

      const chip = document.createElement('span');
      chip.className = `badge badge-lg ${badgeClass} gap-2`;
      chip.dataset.name = name;

      const text = document.createElement('span');
      text.textContent = name;

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-neutral btn-ghost btn-xs btn-circle';
      btn.dataset.action = 'remove-chip';
      btn.textContent = '✕';

      const hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = hiddenInputName;
      hidden.value = name;

      chip.append(text, btn, hidden);
      container.appendChild(chip);
    };

    input.addEventListener('keydown', (evt) => {
      if (evt.key !== 'Enter') return;
      evt.preventDefault();
      const name = input.value.trim();
      if (!name) return;
      addChip(name);
      input.value = '';
      // Clear suggestions if present
      if (suggestions) {
        suggestions.innerHTML = '';
        suggestions.classList.add('hidden');
      }
    });

    // Delegate chip removal
    container.addEventListener('click', (evt) => {
      const btn = evt.target.closest('[data-action="remove-chip"]');
      if (!btn) return;
      const chip = btn.closest('.badge');
      if (!chip) return;

      const inputRefId = chip.dataset.inputId;
      const hiddenInput = inputRefId
        ? document.getElementById(inputRefId)
        : chip.querySelector('input[type="hidden"]');
      chip.remove();
      hiddenInput?.remove();
    });

    // Autocomplete dropdown behavior (if suggestions element exists)
    if (suggestions) {
      input.addEventListener('focus', () => {
        if (suggestions.innerHTML.trim()) suggestions.classList.remove('hidden');
      });

      input.addEventListener('blur', () => {
        setTimeout(() => suggestions.classList.add('hidden'), 200);
      });
    }

    const instance = { input, container, suggestions, addChip, chipExists };
    chipInputs.push(instance);
    return instance;
  };

  // Initialize tags chip input with autocomplete
  initChipInput({
    inputId: 'tag_search',
    containerId: 'tags-chips',
    suggestionsId: 'tag-suggestions',
    hiddenInputName: 'new_tags',
    badgeClass: 'badge-secondary',
  });

  // Initialize contributors chip input with autocomplete
  initChipInput({
    inputId: 'contributor_search',
    containerId: 'contributors-chips',
    suggestionsId: 'contributor-suggestions',
    hiddenInputName: 'new_contributors',
    badgeClass: 'badge-primary',
  });

  // Single set of HTMX event handlers for all chip inputs
  if (window.htmx && chipInputs.length > 0) {
    document.body.addEventListener('htmx:afterSwap', (evt) => {
      const target = evt.detail?.target || evt.target;
      for (const { suggestions } of chipInputs) {
        if (suggestions && target === suggestions) {
          suggestions.classList.toggle('hidden', !suggestions.innerHTML.trim());
        }
      }
    });

    document.body.addEventListener('htmx:beforeRequest', (evt) => {
      const target = evt.detail?.target || evt.target;
      for (const { suggestions } of chipInputs) {
        if (suggestions && target === suggestions) {
          suggestions.classList.add('hidden');
        }
      }
    });

    document.body.addEventListener('htmx:beforeSwap', (evt) => {
      const target = evt.detail?.target || evt.target;
      for (const { input, container, suggestions, chipExists } of chipInputs) {
        if (target !== container) continue;

        const responseHtml = evt.detail?.serverResponse || evt.detail?.xhr?.responseText;
        if (!responseHtml) continue;

        const tmp = document.createElement('div');
        tmp.innerHTML = responseHtml;
        const incomingChip = tmp.querySelector('span[data-id]');
        const incomingId = incomingChip?.dataset.id;

        const incomingName =
          incomingChip?.dataset.name ||
          incomingChip?.querySelector('span')?.textContent ||
          incomingChip?.textContent ||
          '';

        const idExists = incomingId && container.querySelector(`span[data-id="${incomingId}"]`);
        const nameExists = incomingName && chipExists(incomingName);

        if (idExists || nameExists) {
          evt.detail.shouldSwap = false;
          if (suggestions) suggestions.classList.add('hidden');
          input.value = '';
        }
      }
    });
  }
});
