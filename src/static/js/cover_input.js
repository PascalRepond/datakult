// Cover image widget: preview the chosen file, and delete the current cover or the chosen file.
// Listeners are delegated to the document, as this script is loaded in the head with the form media.
// Each change of the chosen file is told to the page by a cover:change event on the widget, whose detail holds
// the file and its data URL, or is null once no file is chosen.

// Show one of the previews of a widget: the existing cover, the chosen file or the placeholder
const showCoverPreview = (widget, preview) => {
  widget.querySelectorAll('[data-preview]').forEach((element) => {
    element.classList.toggle('hidden', element.dataset.preview !== preview);
  });
};

// Without a chosen file, show the existing cover if any, else the placeholder
const showExistingCover = (widget) => {
  showCoverPreview(widget, widget.querySelector('[data-preview="existing"]') ? 'existing' : 'none');
};

const dispatchCoverChange = (widget, detail) => {
  widget.dispatchEvent(new CustomEvent('cover:change', { bubbles: true, detail }));
};

document.addEventListener('change', (event) => {
  const widget = event.target.closest('.cover-widget');
  if (!widget || event.target.type !== 'file') return;

  const file = event.target.files?.[0];
  if (!file) {
    showExistingCover(widget);
    dispatchCoverChange(widget, null);
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    widget.querySelector('[data-preview="new"] img').src = reader.result;
    showCoverPreview(widget, 'new');
    // A new file is uploaded, rather than the cover cleared
    const clearCheckbox = widget.querySelector('input[type="checkbox"]');
    if (clearCheckbox) clearCheckbox.checked = false;
    dispatchCoverChange(widget, { file, dataUrl: reader.result });
  };
  reader.readAsDataURL(file);
});

document.addEventListener('click', (event) => {
  const button = event.target.closest('.cover-widget [data-action]');
  if (!button) return;

  const widget = button.closest('.cover-widget');
  widget.querySelector('input[type="file"]').value = '';
  if (button.dataset.action === 'delete-cover') {
    widget.querySelector('input[type="checkbox"]').checked = true;
    showCoverPreview(widget, 'none');
  } else {
    showExistingCover(widget);
  }
  dispatchCoverChange(widget, null);
});
