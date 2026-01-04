// Interactivity for media edit page: contributors, date picker, and delete confirmation
document.addEventListener('DOMContentLoaded', () => {
  // Set up "Set to today" button for review date
  const setTodayBtn = document.getElementById('set-today-btn');
  const reviewDateInput = document.getElementById('id_review_date');

  if (setTodayBtn && reviewDateInput) {
    setTodayBtn.addEventListener('click', () => {
      reviewDateInput.value = new Date().toISOString().split('T')[0];
    });
  }

  // Contributor chips and autocomplete dropdown
  const input = document.getElementById('contributor_search');
  const suggestions = document.getElementById('contributor-suggestions');
  const chips = document.getElementById('contributors-chips');

  if (!input || !suggestions) return;

  const toggleSuggestionsVisibility = () => {
    const hasContent = suggestions.innerHTML.trim().length > 0;
    suggestions.classList.toggle('hidden', !hasContent);
  };

  // Show suggestions when input is focused
  input.addEventListener('focus', () => {
    if (suggestions.innerHTML.trim()) {
      suggestions.classList.remove('hidden');
    }
  });

  // Hide suggestions shortly after input loses focus
  input.addEventListener('blur', () => {
    setTimeout(() => suggestions.classList.add('hidden'), 200);
  });

  const contributorAlreadyExists = (name) => {
    const lower = name.trim().toLowerCase();
    
    // Check existing chips (from database)
    const existingChips = Array.from(chips?.querySelectorAll('span[data-id], span[data-name]') || []).some(
      (chip) => (chip.dataset.name || chip.textContent || '').trim().toLowerCase() === lower,
    );
    
    // Check new contributors (created dynamically)
    const newContributors = Array.from(document.querySelectorAll('input[name="new_contributors"]')).some(
      (inp) => inp.value.trim().toLowerCase() === lower,
    );
    
    return existingChips || newContributors;
  };

  const addNewContributorChip = (name) => {
    if (!name || contributorAlreadyExists(name)) return;

    const chip = document.createElement('span');
    chip.className = 'badge badge-lg badge-primary gap-2';
    chip.dataset.name = name;

    const text = document.createElement('span');
    text.textContent = name;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-ghost btn-xs btn-circle';
    btn.dataset.action = 'remove-chip';
    btn.textContent = '✕';

    const hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.name = 'new_contributors';
    hidden.value = name;

    chip.append(text, btn, hidden);
    chips?.appendChild(chip);
  };

  input.addEventListener('keydown', (evt) => {
    if (evt.key !== 'Enter') return;

    const name = input.value.trim();
    if (!name) return;

    evt.preventDefault();
    addNewContributorChip(name);
    input.value = '';
    suggestions.innerHTML = '';
    suggestions.classList.add('hidden');
  });

  // Show/hide dropdown when htmx swaps new content into the suggestions box
  if (window.htmx) {
    document.body.addEventListener('htmx:afterSwap', (evt) => {
      const target = evt.detail?.target || evt.target;
      if (target === suggestions) {
        toggleSuggestionsVisibility();
      }
    });

    document.body.addEventListener('htmx:beforeRequest', (evt) => {
      const target = evt.detail?.target || evt.target;
      if (target === suggestions) {
        suggestions.classList.add('hidden');
      }
    });

    document.body.addEventListener('htmx:beforeSwap', (evt) => {
      const target = evt.detail?.target || evt.target;
      if (target !== chips) return;

      const responseHtml = evt.detail?.serverResponse || evt.detail?.xhr?.responseText;
      if (!responseHtml) return;

      const tmp = document.createElement('div');
      tmp.innerHTML = responseHtml;
      const incomingChip = tmp.querySelector('span[data-id]');
      const incomingId = incomingChip?.dataset.id;

      if (incomingId && chips.querySelector(`span[data-id="${incomingId}"]`)) {
        evt.detail.shouldSwap = false;
        suggestions.classList.add('hidden');
        input.value = '';
      }
    });
  }

  // Delegate chip removal so it also works for htmx-inserted chips
  chips?.addEventListener('click', (evt) => {
    const btn = evt.target.closest('[data-action="remove-chip"]');
    if (!btn) return;

    const chip = btn.closest('span');
    if (!chip) return;

    const inputId = chip.dataset.inputId;
    const hiddenInput = inputId
      ? document.getElementById(inputId)
      : chip.querySelector('input[type="hidden"]') || document.querySelector(`input[name="contributors"][value="${chip.dataset.id}"]`);

    chip.remove();
    hiddenInput?.remove();
  });
});
