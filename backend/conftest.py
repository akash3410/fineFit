"""Pytest bootstrap for the FineFit backend test suite.

``pytest``'s ``pythonpath`` ini option is resolved relative to the rootdir, which
can change depending on the directory pytest is invoked from (terminal, IDE
test runner, CI).  The project uses two import roots:

* ``backend/``        -> ``config.settings.*``, ``manage.py``
* ``backend/apps/``   -> ``apps.<app_name>.*``

Inserting both here keeps imports such as ``from apps.accounts.models import
CustomUser`` working regardless of the working directory or the runner used.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent

for path in (BACKEND_DIR, BACKEND_DIR / "apps"):
    resolved = str(path)
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
