import frappe

from smart_school.users import ensure_role


def execute():
	"""Guardians use the portal only:
	- Parent gets no desk permissions and no desk access, so parent users become Website Users;
	- each Guardian is linked to the User of its own email;
	- users that are not linked to any Guardian lose the Parent role."""
	frappe.db.delete("Custom DocPerm", {"role": "Parent"})

	for guardian in frappe.get_all(
		"Guardian", filters={"email": ["is", "set"]}, fields=["name", "email", "user"]
	):
		email_user = frappe.db.exists("User", guardian.email)
		if email_user and email_user != guardian.user:
			frappe.db.set_value("Guardian", guardian.name, "user", email_user)

	guardian_users = set(frappe.get_all("Guardian", filters={"user": ["is", "set"]}, pluck="user"))
	parent_users = frappe.get_all(
		"Has Role", filters={"role": "Parent", "parenttype": "User"}, pluck="parent"
	)
	for user in set(parent_users) - guardian_users:
		if frappe.db.exists("User", user):
			frappe.get_doc("User", user).remove_roles("Parent")

	for user in guardian_users:
		ensure_role(user, "Parent")

	# Role.on_update re-evaluates user_type for every user with this role
	role = frappe.get_doc("Role", "Parent")
	role.desk_access = 0
	role.save()
