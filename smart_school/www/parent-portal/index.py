import frappe
from frappe import _

def get_context(context):
    # Hakikisha mtu ameingia (logged in)
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to view this page"), frappe.PermissionError)

    # Pata Guardian record inayolingana na huyu User
    guardian_name = frappe.db.get_value("Guardian", {"user": frappe.session.user}, "name")

    if not guardian_name:
        frappe.throw(_("No guardian profile linked to this account"))

    guardian = frappe.get_doc("Guardian", guardian_name)

    # Pata watoto wote kupitia child table
    children = []
    for row in guardian.students:
        student = frappe.get_doc("Student", row.student)
        children.append(student)

    context.guardian = guardian
    context.children = children
    context.no_cache = 1