// Interactivity for contributor chips and autocomplete dropdown
document.addEventListener('DOMContentLoaded', () => {
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
    
    // Cherche dans les chips existants (depuis la base de données)
    const existingChips = Array.from(chips?.querySelectorAll('span[data-id], span[data-name]') || []).some(
      (chip) => (chip.dataset.name || chip.textContent || '').trim().toLowerCase() === lower,
    );
    
    // Cherche dans les nouveaux contributeurs (créés dynamiquement)
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

    const firstSuggestion = suggestions.querySelector('a');
    if (firstSuggestion) {
      evt.preventDefault();
      firstSuggestion.click();
      return;
    }

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
