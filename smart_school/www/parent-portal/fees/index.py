import frappe
from smart_school.an_intergrated_academic_management_system.doctype.smart_school_settings.smart_school_settings import (
    demo_payments_enabled,
)
from smart_school.fees import get_fee_statement
from smart_school.portal_utils import get_logged_in_guardian, get_children, get_notifications

def get_context(context):
    guardian = get_logged_in_guardian()
    children = get_children(guardian)
    if not children:
        frappe.throw("No children linked to this account")

    selected_id = frappe.form_dict.get("student") or children[0].name
    selected_student = next((c for c in children if c.name == selected_id), children[0])

    # Historia kamili ya malipo (kwa kuonekana tu, si kwa mahesabu ya balance)
    payments = frappe.get_all(
        "Fee Payment",
        filters={"student": selected_student.name},
        fields=["name", "term", "amount_paid", "payment_date", "payment_method", "status", "receipt_number"],
        order_by="payment_date desc, creation desc"
    )
    for p in payments:
        p.term_name = frappe.get_cached_value("Term", p.term, "term_name")

    # Muhtasari kwa kila term kutoka get_fee_statement (chanzo kimoja cha ukweli)
    statement = get_fee_statement(selected_student.name)

    context.guardian = guardian
    context.children = children
    context.selected_student = selected_student
    context.payments = payments
    context.summary_list = [r for r in statement.rows if r.is_due]
    context.upcoming_list = [r for r in statement.rows if not r.is_due]
    context.current_balance = statement.balance
    context.payments_enabled = demo_payments_enabled()
    notif_data = get_notifications(guardian, children)
    context.notifications = notif_data["items"]
    context.unseen_count = notif_data["unseen_count"]
    context.no_cache = 1
