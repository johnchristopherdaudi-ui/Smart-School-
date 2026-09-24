import frappe
from smart_school.parent_dashboard import get_dashboard
from smart_school.portal_utils import get_portal_guardian, get_children, get_notifications

def get_context(context):
    guardian = get_portal_guardian()
    children = get_children(guardian)

    selected_student = None
    if children:
        selected_id = frappe.form_dict.get("student") or children[0].name
        selected_student = next((c for c in children if c.name == selected_id), children[0])

    context.guardian = guardian
    context.children = children
    context.selected_student = selected_student
    context.dashboard = get_dashboard(selected_student) if selected_student else None
    notif_data = get_notifications(guardian, children)
    context.notifications = notif_data["items"]
    context.unseen_count = notif_data["unseen_count"]
    context.no_cache = 1
