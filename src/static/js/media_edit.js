// Interactivity for media edit page: chips (contributors, tags) and date picker

document.addEventListener('DOMContentLoaded', () => {
  // Set up "Set to today" button for review date
  const setTodayBtn = document.getElementById('set-today-btn');
  const reviewDateInput = document.getElementById('id_review_date');

  if (setTodayBtn && reviewDateInput) {
    setTodayBtn.addEventListener('click', () => {
      // The local date, where toISOString would give the UTC one
      const today = new Date();
      const pad = (number) => String(number).padStart(2, '0');
      reviewDateInput.value = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
    });
  }

  // A chosen cover file takes the place of the imported cover, which comes back once the file is removed
  const importCoverUrlInput = document.getElementById('import-cover-url');
  const importPosterPreview = document.getElementById('import-poster-preview');

  if (importPosterPreview) {
    const imported = { url: importCoverUrlInput.value, src: importPosterPreview.src, alt: importPosterPreview.alt };
    document.addEventListener('cover:change', (event) => {
      const chosen = event.detail;
      importCoverUrlInput.value = chosen ? '' : imported.url;
      importPosterPreview.src = chosen ? chosen.dataUrl : imported.src;
      importPosterPreview.alt = chosen ? chosen.file.name : imported.alt;
    });
  }

  // Store all chip inputs for HTMX event handling
  const chipInputs = [];

  // Generic chip input handler with optional HTMX autocomplete support
  const initChipInput = ({ inputId, containerId, suggestionsId, templateId }) => {
    const input = document.getElementById(inputId);
    const container = document.getElementById(containerId);
    const suggestions = suggestionsId ? document.getElementById(suggestionsId) : null;
    const template = document.getElementById(templateId);
    if (!input || !container || !template) return;

    const chipExists = (name) => {
      const lower = name.trim().toLowerCase();
      return Array.from(container.querySelectorAll('.badge')).some(
        (badge) => (badge.dataset.name || '').trim().toLowerCase() === lower
      );
    };

    // Clone the server-rendered chip template, so new chips look like the existing ones
    const addChip = (name) => {
      if (!name || chipExists(name)) return;

      const chip = template.content.firstElementChild.cloneNode(true);
      chip.dataset.name = name;
      chip.querySelector('.chip-name').textContent = name;
      chip.querySelector('input[type="hidden"]').value = name;
      const btn = chip.querySelector('[data-action="remove-chip"]');
      btn.setAttribute('aria-label', btn.getAttribute('aria-label').replace('{name}', name));
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

    // Delegate chip removal (the hidden input goes with its chip)
    container.addEventListener('click', (evt) => {
      const btn = evt.target.closest('[data-action="remove-chip"]');
      btn?.closest('.badge')?.remove();
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

    chipInputs.push({ input, container, suggestions, chipExists });
  };

  // Initialize tags chip input with autocomplete
  initChipInput({
    inputId: 'tag_search',
    containerId: 'tags-chips',
    suggestionsId: 'tag-suggestions',
    templateId: 'new-tag-chip',
  });

  // Initialize contributors chip input with autocomplete
  initChipInput({
    inputId: 'contributor_search',
    containerId: 'contributors-chips',
    suggestionsId: 'contributor-suggestions',
    templateId: 'new-contributor-chip',
  });

  // Single set of HTMX event handlers for all chip inputs
  if (chipInputs.length > 0) {
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

        const incomingName = incomingChip?.dataset.name || '';

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
