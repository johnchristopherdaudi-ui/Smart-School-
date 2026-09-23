import frappe


def execute():
    """Teachers created before Teacher.user existed get a User (role Teacher) from their email.
    No welcome email here; they can set a password through "Forgot Password"."""
    teachers = frappe.get_all("Teacher", filters={"email": ["is", "set"], "user": ["is", "not set"]}, pluck="name")
    for name in teachers:
        frappe.get_doc("Teacher", name).create_user(send_welcome_email=False)
