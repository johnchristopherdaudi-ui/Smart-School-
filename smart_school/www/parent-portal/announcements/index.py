import frappe
from smart_school.portal_utils import get_logged_in_guardian, get_children, get_notification_count

def get_context(context):
    guardian = get_logged_in_guardian()
    children = get_children(guardian)

    class_map = {}
    for child in children:
        if child.current_class:
            class_map.setdefault(child.current_class, []).append(child.full_name)

    announcements = []
    if class_map:
        announcements = frappe.get_all(
            "Announcement",
            filters={"class": ["in", list(class_map.keys())]},
            fields=["name", "tittle", "message", "date", "class", "posted_by"],
            order_by="date desc"
        )
        for a in announcements:
            a["for_students"] = ", ".join(class_map.get(a["class"], []))

    context.guardian = guardian
    context.children = children
    context.announcements = announcements
    context.notification_count = get_notification_count(children)
    context.no_cache = 1
