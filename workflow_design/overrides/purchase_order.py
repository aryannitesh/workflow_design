"""
Dashboard override for Purchase Order.
Registered in hooks.py → override_doctype_dashboards.
"""


def get_dashboard_data(data):
    """Return the standard dashboard data unchanged."""
    return data
