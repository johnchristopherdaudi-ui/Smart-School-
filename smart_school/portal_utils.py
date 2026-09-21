import frappe
from frappe.utils import add_days, nowdate


def get_logged_in_guardian():
    if frappe.session.user == "Guest":
        frappe.throw("Please login to view this page", frappe.PermissionError)

    guardian_name = frappe.db.get_value("Guardian", {"user": frappe.session.user}, "name")
    if not guardian_name:
        frappe.throw("No guardian profile linked to this account")

    return frappe.get_doc("Guardian", guardian_name)


def get_children(guardian):
    children = []
    for row in guardian.students:
        student = frappe.get_doc("Student", row.student)
        parts = (student.full_name or "").split()
        student.initials = "".join([p[0].upper() for p in parts[:2]]) if parts else "?"
        children.append(student)
    return children


def get_notifications(children):
    """Rudisha list ya notifications halisi (kila moja na message + link)."""
    notifications = []
    if not children:
        return notifications

    student_names = [c.name for c in children]
    student_map = {c.name: c.full_name for c in children}

    unpaid = frappe.get_all(
        "Fee Payment",
        filters={"student": ["in", student_names], "balance": [">", 0]},
        fields=["student", "term", "balance"]
    )
    for u in unpaid:
        term_name = frappe.get_cached_value("Term", u.term, "term_name") or u.term
        notifications.append({
            "type": "fee",
            "message": f"{student_map.get(u.student, u.student)}: Deni la {u.balance:,.0f} TZS ({term_name})",
            "link": f"/parent-portal/fees?student={u.student}"
        })

    class_names = list({c.current_class for c in children if c.current_class})
    if class_names:
        recent_announcements = frappe.get_all(
            "Announcement",
            filters={"class": ["in", class_names], "date": [">=", add_days(nowdate(), -7)]},
            fields=["tittle", "class"]
        )
        for a in recent_announcements:
            notifications.append({
                "type": "announcement",
                "message": f"Tangazo jipya: {a.tittle}",
                "link": "/parent-portal/announcements"
            })

    return notifications


def get_notification_count(children):
    return len(get_notifications(children))
