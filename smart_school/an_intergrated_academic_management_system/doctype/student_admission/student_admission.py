import frappe
from frappe.model.document import Document

APPROVER_ROLES = ("Headmaster", "System Manager")


class StudentAdmission(Document):
    def validate(self):
        self.validate_status_change()

    def validate_status_change(self):
        # Status is also settable through the API, so enforce approvers here, not only via doctype permissions
        if self.status == "Pending" or not self.has_value_changed("status"):
            return

        if not set(APPROVER_ROLES) & set(frappe.get_roles()):
            frappe.throw(
                "Only a Headmaster or System Manager can approve or reject an admission",
                frappe.PermissionError,
            )

    def on_update(self):
        if self.status == "Approved" and not self.student:
            student = frappe.new_doc("Student")
            student.full_name = self.full_name
            student.date_of_birth = self.date_of_birth
            student.status = "Active"
            student.admission_date = frappe.utils.today()
            student.current_class = self.class_applying
            student.admission_reference = self.name

            student.insert(ignore_permissions=True)

            self.db_set("student", student.name)
            frappe.msgprint(f"Student record created: {student.name}")