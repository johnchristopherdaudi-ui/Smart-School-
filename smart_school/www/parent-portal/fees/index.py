import frappe
from smart_school.portal_utils import get_logged_in_guardian, get_children, get_notifications

def get_context(context):
    guardian = get_logged_in_guardian()
    children = get_children(guardian)
    if not children:
        frappe.throw("No children linked to this account")

    selected_id = frappe.form_dict.get("student") or children[0].name
    selected_student = next((c for c in children if c.name == selected_id), children[0])

    payments = frappe.get_all(
        "Fee Payment",
        filters={"student": selected_student.name},
        fields=["term", "amount_paid", "payment_date", "payment_method", "status", "receipt_number", "balance", "overpayment"],
        order_by="payment_date desc"
    )

    for p in payments:
        term_doc = frappe.get_cached_doc("Term", p.term)
        p.term_name = term_doc.term_name

    current_balance = payments[0].balance if payments else 0

    context.guardian = guardian
    context.children = children
    context.selected_student = selected_student
    context.payments = payments
    context.current_balance = current_balance
    notif_data = get_notifications(guardian, children)
    context.notifications = notif_data["items"]
    context.unseen_count = notif_data["unseen_count"]
    context.no_cache = 1
