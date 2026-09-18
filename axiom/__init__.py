import os
# Make the top‑level ``axiom`` package a namespace that points to the ``backend/axiom`` directory.
# This allows imports like ``from axiom.config import Settings`` to resolve correctly.
__path__ = [os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "axiom"))]
