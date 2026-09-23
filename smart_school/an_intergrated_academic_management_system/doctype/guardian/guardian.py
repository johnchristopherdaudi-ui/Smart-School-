import frappe
from frappe.model.document import Document

from smart_school.users import assert_user_not_linked, ensure_role, ensure_user_with_role


class Guardian(Document):
    def validate(self):
        if self.email:
            self.email = self.email.strip()
            other = frappe.db.get_value("Guardian", {"email": self.email, "name": ["!=", self.name]}, "name")
            if other:
                frappe.throw(f"Guardian {other} already uses the email {self.email}")

        if self.user:
            assert_user_not_linked("Guardian", self.user, self.name)

    def on_update(self):
        if self.email and not self.user:
            self.create_portal_user()
        elif self.user:
            ensure_role(self.user, "Parent")

    def create_portal_user(self):
        user_name = ensure_user_with_role(self.email, self.full_name, "Parent")
        assert_user_not_linked("Guardian", user_name, self.name)
        self.db_set("user", user_name)
