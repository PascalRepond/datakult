// Backup page: ask to confirm the import once a backup file is chosen, else say that one is missing
document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-action="confirm-import"]');
  if (!button) return;

  if (button.form.checkValidity()) {
    document.getElementById(button.dataset.modal).showModal();
  } else {
    button.form.reportValidity();
  }
});
