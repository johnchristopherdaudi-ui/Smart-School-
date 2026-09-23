import frappe
from smart_school.portal_utils import get_logged_in_guardian

def get_context(context):
    guardian = get_logged_in_guardian()

    reference = frappe.form_dict.get("ref")
    term = frappe.form_dict.get("term")

    log = frappe.get_doc("Payment Gateway Log", {"transaction_reference": reference})

    # Hakikisha huyu guardian ndiye mwenye ruhusa ya log hii
    allowed_students = [row.student for row in guardian.students]
    if log.student not in allowed_students:
        frappe.throw("Huna ruhusa ya kufikia malipo haya")

    context.log = log
    context.term = term
    context.reference = reference
    context.no_cache = 1
