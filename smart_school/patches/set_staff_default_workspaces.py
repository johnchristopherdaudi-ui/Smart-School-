import frappe

from smart_school.users import ROLE_WORKSPACES, set_default_workspace


def execute():
	"""Existing staff users open their role's workspace after login (new logins are handled by on_session_creation)."""
	roles = [role for role, _ in ROLE_WORKSPACES]
	users = frappe.get_all(
		"Has Role", filters={"parenttype": "User", "role": ["in", roles]}, pluck="parent", distinct=True
	)
	for user in users:
		if frappe.db.get_value("User", user, "enabled"):
			set_default_workspace(user=user)
