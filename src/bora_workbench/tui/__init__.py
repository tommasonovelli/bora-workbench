"""Contain the optional terminal presentation without importing Textual eagerly.

The CLI imports terminal capability checks before it imports the application so a non-interactive
invocation can fail with exit code 2 without loading Textual (D-086, TUI plan E1).
"""
