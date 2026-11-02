"""Compliance Assistant agent package.

Public entry points (added in build steps 3-6):
    run_turn(user, message)      -> generator over graph events
    resume_turn(user, decision)  -> resumes an interrupted thread (DPO approval)

Nothing in this package knows the UI: the web API (api/) and the React pages (web/) sit on top of it.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
