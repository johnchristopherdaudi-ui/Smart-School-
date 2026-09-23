import frappe
from frappe.utils.html_utils import sanitize_html
from smart_school.portal_utils import get_logged_in_guardian, get_children, get_notifications

def get_context(context):
    guardian = get_logged_in_guardian()
    children = get_children(guardian)

    class_map = {}
    for child in children:
        if child.current_class:
            class_map.setdefault(child.current_class, []).append(child.full_name)

    announcements = []
    if class_map:
        class_names = list(class_map.keys())

        # Pata majina ya Announcement zenye angalau class moja inayolingana
        announcement_names = frappe.get_all(
            "Announcement Class",
            filters={"class": ["in", class_names]},
            pluck="parent",
            distinct=True
        )

        if announcement_names:
            raw_announcements = frappe.get_all(
                "Announcement",
                filters={"name": ["in", announcement_names]},
                fields=["name", "tittle", "message", "date", "posted_by"],
                order_by="date desc"
            )

            for a in raw_announcements:
                # Pata class zote za tangazo hili
                doc_classes = frappe.get_all(
                    "Announcement Class",
                    filters={"parent": a.name},
                    pluck="class"
                )
                # Onyesha ni watoto gani wa guardian huyu wanahusika
                relevant_students = []
                for c in doc_classes:
                    relevant_students.extend(class_map.get(c, []))

                # message is a Text Editor field: keep its formatting, strip anything unsafe
                a["message"] = sanitize_html(a.message or "", always_sanitize=True)
                a["class_list"] = ", ".join(doc_classes)
                a["for_students"] = ", ".join(set(relevant_students))
                announcements.append(a)

    context.guardian = guardian
    context.children = children
    context.announcements = announcements
    notif_data = get_notifications(guardian, children)
    context.notifications = notif_data["items"]
    context.unseen_count = notif_data["unseen_count"]
    context.no_cache = 1
