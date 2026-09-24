import frappe
from smart_school.fees import get_fee_statement
from smart_school.results import get_portal_results
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

    # Muhtasari wa term ya karibuni uliochapishwa kikamilifu
    published_terms = [r for r in get_portal_results(selected_student.name) if r.summary]
    latest_result = None
    if published_terms:
        latest = published_terms[-1]
        latest_result = frappe._dict(latest.summary, term_name=latest.term_name)

    current_balance = get_fee_statement(selected_student.name).balance

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
