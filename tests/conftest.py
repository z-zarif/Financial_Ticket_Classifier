"""Shared fixtures for the test suite.

The repo root must be importable so `import app` resolves the FastAPI
module. We achieve that by prepending the repo root to sys.path.
"""

from __future__ import annotations

import os
import sys

# Make the repo root importable for `from app import app` etc.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
