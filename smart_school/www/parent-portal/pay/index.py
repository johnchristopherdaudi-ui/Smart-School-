import frappe
from smart_school.portal_utils import get_logged_in_guardian, get_children

def get_context(context):
    guardian = get_logged_in_guardian()
    children = get_children(guardian)

    student_id = frappe.form_dict.get("student")
    term = frappe.form_dict.get("term")
    amount = frappe.form_dict.get("amount")

    allowed_ids = [c.name for c in children]
    if student_id not in allowed_ids:
        frappe.throw("Huna ruhusa ya kulipia mwanafunzi huyu")

    selected_student = next(c for c in children if c.name == student_id)
    term_name = frappe.get_cached_value("Term", term, "term_name") if term else ""

    context.guardian = guardian
    context.selected_student = selected_student
    context.term = term
    context.term_name = term_name
    context.amount = amount
    context.no_cache = 1
