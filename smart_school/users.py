import frappe


def ensure_user_with_role(email, full_name, role, send_welcome_email=True):
    """Return the User for this email, creating it if needed, and make sure it has the role."""
    user_name = frappe.db.exists("User", email)
    if not user_name:
        user = frappe.new_doc("User")
        user.email = email
        user.first_name = full_name
        user.send_welcome_email = 1 if send_welcome_email else 0
        user.append("roles", {"role": role})
        user.insert(ignore_permissions=True)
        return user.name

    ensure_role(user_name, role)
    return user_name


def ensure_role(user_name, role):
    if role in frappe.get_roles(user_name):
        return

    user = frappe.get_doc("User", user_name)
    user.flags.ignore_permissions = True
    user.add_roles(role)


def assert_user_not_linked(doctype, user_name, name):
    """One User may belong to only one Guardian / Teacher."""
    other = frappe.db.get_value(doctype, {"user": user_name, "name": ["!=", name]}, "name")
    if other:
        frappe.throw(f"User {user_name} is already linked to {doctype} {other}")
