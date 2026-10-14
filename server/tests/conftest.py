"""Point every test at a throwaway database before the app is imported.

The engine is built from settings at import time, so this has to run first.
Without it, test_create_tables_runs ran `create_all` against the dev database —
creating tables ahead of their Alembic migration, which then failed on startup.
"""

import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix='ragkit-test-')}/test.db"
