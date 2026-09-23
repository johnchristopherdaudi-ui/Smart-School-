import frappe
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
        term_doc = frappe.get_cached_doc("Term", p.term)
        p.term_name = term_doc.term_name

    # Muhtasari LIVE kwa kila term (hii ndiyo chanzo cha ukweli, si record moja)
    term_summary = {}
    for p in payments:
        if p.term not in term_summary:
            term_summary[p.term] = {"term_name": p.term_name, "total_paid": 0}
        term_summary[p.term]["total_paid"] += p.amount_paid or 0

    for term, info in term_summary.items():
        fee_structure = frappe.get_all(
            "Fee Structure",
            filters={"class": selected_student.current_class, "term": term},
            fields=["amount"]
        )
        amount_due = fee_structure[0].amount if fee_structure else 0
        info["amount_due"] = amount_due
        info["remaining"] = max(amount_due - info["total_paid"], 0)
        info["overpaid"] = max(info["total_paid"] - amount_due, 0) if amount_due else 0

    summary_list = [{"term": t, **info} for t, info in term_summary.items()]

    current_balance = sum(s["remaining"] for s in summary_list)

    context.guardian = guardian
    context.children = children
    context.selected_student = selected_student
    context.payments = payments
    context.summary_list = summary_list
    context.current_balance = current_balance
    notif_data = get_notifications(guardian, children)
    context.notifications = notif_data["items"]
    context.unseen_count = notif_data["unseen_count"]
    context.no_cache = 1
