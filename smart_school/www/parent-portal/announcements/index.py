import frappe
from frappe.utils.html_utils import sanitize_html
from smart_school.portal_utils import get_announcements, get_logged_in_guardian, get_children, get_notifications

def get_context(context):
    guardian = get_logged_in_guardian()
    children = get_children(guardian)

    class_map = {}
    for child in children:
        if child.current_class:
            class_map.setdefault(child.current_class, []).append(child.full_name)

    announcements = []
    for a in get_announcements(list(class_map), fields=("name", "title", "message", "date", "posted_by", "audience")):
        if a.audience == "All School":
            doc_classes = ["Shule nzima"]
            relevant_students = [c.full_name for c in children]
        else:
            # Pata class zote za tangazo hili na watoto wa guardian huyu wanaohusika
            doc_classes = frappe.get_all("Announcement Class", filters={"parent": a.name}, pluck="class")
            relevant_students = [name for c in doc_classes for name in class_map.get(c, [])]

        # message is a Text Editor field: keep its formatting, strip anything unsafe
        a["message"] = sanitize_html(a.message or "", always_sanitize=True)
        a["class_list"] = ", ".join(doc_classes)
        a["for_students"] = ", ".join(dict.fromkeys(relevant_students))
        announcements.append(a)

    context.guardian = guardian
    context.children = children
    context.announcements = announcements
    notif_data = get_notifications(guardian, children)
    context.notifications = notif_data["items"]
    context.unseen_count = notif_data["unseen_count"]
    context.no_cache = 1
