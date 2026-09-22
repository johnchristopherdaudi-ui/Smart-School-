import frappe
from smart_school.portal_utils import get_logged_in_guardian, get_children, get_notifications

def get_context(context):
    guardian = get_logged_in_guardian()
    children = get_children(guardian)
    if not children:
        frappe.throw("No children linked to this account")

    student_id = frappe.form_dict.get("student") or children[0].name
    selected_student = next((c for c in children if c.name == student_id), None)
    if not selected_student:
        frappe.throw("Huwezi kuona taarifa za mwanafunzi huyu")

    latest_result = frappe.get_all(
        "Student Term Result",
        filters={"student": selected_student.name},
        fields=["term", "average", "division_display", "division"],
        order_by="creation desc",
        limit=1
    )
    latest_result = latest_result[0] if latest_result else None
    if latest_result:
        latest_result["term_name"] = frappe.get_cached_value("Term", latest_result["term"], "term_name")

    latest_payment = frappe.get_all(
        "Fee Payment",
        filters={"student": selected_student.name},
        fields=["balance"],
        order_by="payment_date desc",
        limit=1
    )
    current_balance = latest_payment[0].balance if latest_payment else 0

    discipline_count = frappe.db.count("Discipline Record", filters={"student": selected_student.name})

    context.guardian = guardian
    context.children = children
    context.selected_student = selected_student
    context.latest_result = latest_result
    context.current_balance = current_balance
    context.discipline_count = discipline_count
    notif_data = get_notifications(guardian, children)
    context.notifications = notif_data["items"]
    context.unseen_count = notif_data["unseen_count"]
    context.no_cache = 1
