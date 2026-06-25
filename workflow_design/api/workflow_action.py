"""
Whitelisted endpoint to apply a workflow action on behalf of the current user.
This avoids requiring the calling user to have direct 'Workflow' doctype read access.
"""

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow


@frappe.whitelist()
def apply_action(doctype: str, docname: str, action: str):
    """
    Apply a workflow action on a document.

    Args:
        doctype:  The doctype name (e.g. "Material Request")
        docname:  The document name
        action:   The workflow action to apply (e.g. "WD Submit for Approval")

    Returns:
        The updated document as a dict.
    """
    # Ensure the user has at least read access on the document
    frappe.has_permission(doctype, ptype="read", doc=docname, throw=True)

    doc = frappe.get_doc(doctype, docname)
    apply_workflow(doc, action)

    return frappe.get_doc(doctype, docname).as_dict()
