import frappe
from frappe.model.document import Document

class StudentAdmission(Document):
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