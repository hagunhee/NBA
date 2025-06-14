# src/gui/dialogs/__init__.py
from .task_edit_dialog import TaskEditDialog
from .license_dialog import LicenseDialog

# from .help_dialog import HelpDialog

try:
    from .task_edit_dialog import TaskEditDialog
except ImportError:
    TaskEditDialog = None

try:
    from .license_dialog import LicenseDialog
except ImportError:
    LicenseDialog = None
