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


# Workspace each staff role lands on after login (first match wins)
ROLE_WORKSPACES = (
    ("Headmaster", "Headmaster"),
    ("Accountant", "Finance"),
    ("Teacher", "Academics"),
    ("System Manager", "School Settings"),
)


def set_default_workspace(login_manager=None, user=None):
    """on_session_creation: open the role's workspace after login. A workspace the user picked
    themselves (not one of ours) is left alone."""
    user = user or frappe.session.user
    if user in ("Administrator", "Guest"):
        return

    roles = set(frappe.get_roles(user))
    target = next((workspace for role, workspace in ROLE_WORKSPACES if role in roles), None)
    current = frappe.db.get_value("User", user, "default_workspace")
    ours = {workspace for _, workspace in ROLE_WORKSPACES}
    if target and current != target and (not current or current in ours):
        frappe.db.set_value("User", user, "default_workspace", target, update_modified=False)
