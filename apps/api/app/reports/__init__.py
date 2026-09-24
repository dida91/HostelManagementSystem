"""Report rendering: a neutral Report model, rendered to Excel or PDF.

The data is assembled in app/services/reports.py; nothing in this package
touches the database, which keeps the renderers trivially testable.
"""
