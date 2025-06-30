"""Utility functions for Phantom Power Monitoring."""
from __future__ import annotations


def sanitize_name(name: str) -> str:
    """Sanitize a name for use in entity IDs."""
    return name.lower().replace(" ", "_").replace("-", "_")