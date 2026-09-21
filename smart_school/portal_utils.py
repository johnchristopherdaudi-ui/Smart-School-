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


def get_notification_count(children):
    if not children:
        return 0

    student_names = [c.name for c in children]
    unpaid_count = frappe.db.count(
        "Fee Payment",
        filters={"student": ["in", student_names], "balance": [">", 0]}
    )

    class_names = list({c.current_class for c in children if c.current_class})
    recent_announcements = 0
    if class_names:
        recent_announcements = frappe.db.count(
            "Announcement",
            filters={"class": ["in", class_names], "date": [">=", add_days(nowdate(), -7)]}
        )

    return unpaid_count + recent_announcements
