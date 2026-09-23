# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from smart_school.users import assert_user_not_linked, ensure_role, ensure_user_with_role


class Teacher(Document):
	def on_update(self):
		if self.email and not self.user:
			self.create_user()
		elif self.user:
			ensure_role(self.user, "Teacher")

	def create_user(self, send_welcome_email=True):
		user_name = ensure_user_with_role(self.email.strip(), self.full_name, "Teacher", send_welcome_email)
		assert_user_not_linked("Teacher", user_name, self.name)
		self.db_set("user", user_name)
