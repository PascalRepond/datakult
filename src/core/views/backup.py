"""Views of the backup page: export and import of the whole database and media files."""

import tarfile
import tempfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from core.utils import backup_filename, write_backup


@login_required
def backup_manage(request):
    """Display backup management page."""
    return render(request, "base/backup_manage.html")


@login_required
def backup_export(request):
    """Download a backup, written to a temporary file rather than kept on the server."""
    # FileResponse closes the file once it is sent, which deletes it
    archive = tempfile.TemporaryFile()  # noqa: SIM115
    try:
        write_backup(archive)
    except (OSError, CommandError, tarfile.TarError) as e:
        archive.close()
        messages.error(request, _("Backup creation failed: %(error)s") % {"error": str(e)})
        return redirect("backup_manage")

    archive.seek(0)
    return FileResponse(archive, as_attachment=True, filename=backup_filename())


@login_required
def backup_import(request):
    """Import a backup file, which replaces all the data."""
    if request.method != "POST":
        return redirect("backup_manage")

    backup_file = request.FILES.get("backup_file")
    if not backup_file:
        messages.error(request, _("No file selected"))
        return redirect("backup_manage")
    if not backup_file.name.endswith(".tar.gz"):
        messages.error(request, _("Invalid file format. Use a .tar.gz file"))
        return redirect("backup_manage")

    try:
        # The uploaded file is saved for the import command, and deleted once it is imported
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete_on_close=False) as archive:
            for chunk in backup_file.chunks():
                archive.write(chunk)
            archive.close()
            call_command("import_backup", archive.name, "--flush", verbosity=1)
    except (OSError, CommandError, tarfile.TarError) as e:
        messages.error(request, _("Backup import failed: %(error)s") % {"error": str(e)})
        return redirect("backup_manage")

    messages.success(request, _("Backup imported successfully! All data has been restored."))
    return redirect("home")
