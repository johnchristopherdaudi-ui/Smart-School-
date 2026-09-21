import frappe
from frappe.model.document import Document

class Guardian(Document):
    def after_insert(self):
        if self.email and not self.user:
            self.create_portal_user()

    def create_portal_user(self):
        if frappe.db.exists("User", self.email):
            user_name = self.email
        else:
            user = frappe.new_doc("User")
            user.email = self.email
            user.first_name = self.full_name
            user.send_welcome_email = 1
            user.user_type = "Website User"
            user.append("roles", {"role": "Parent"})
            user.insert(ignore_permissions=True)
            user_name = user.name

        self.db_set("user", user_name)