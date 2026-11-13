"""Disabled-by-default paper recorders.

Importing this package does not select a route, does not read credentials, and
does not contact a broker. Construct ``PaperBoundary`` and leave recording off.
"""

from veytrix_execution.boundary import PaperBoundary

__all__ = ["PaperBoundary"]
