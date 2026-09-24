import re

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

		if self.status == "Approved" and not (self.birth_certificate or self.birth_certificate_verified):
			frappe.throw("Attach the birth certificate or tick Birth Certificate Verified before approving")

	def on_update(self):
		if self.status == "Approved" and not self.student:
			student = self.create_student()
			self.db_set("student", student)
			guardian = self.link_guardian(student)
			frappe.msgprint(f"Student record created: {student} (Guardian {guardian})")

	def create_student(self):
		student = frappe.new_doc("Student")
		student.full_name = self.full_name
		student.date_of_birth = self.date_of_birth
		student.gender = self.gender
		student.status = "Active"
		student.admission_date = frappe.utils.today()
		student.current_class = self.class_applying
		student.admission_reference = self.name
		student.insert(ignore_permissions=True)
		return student.name

	def link_guardian(self, student):
		guardian_name = self.find_guardian()
		if guardian_name:
			guardian = frappe.get_doc("Guardian", guardian_name)
		else:
			guardian = frappe.new_doc("Guardian")
			guardian.full_name = self.parent_name
			guardian.phone = self.phone_number
			guardian.email = self.email

		guardian.append("students", {"student": student, "relationship": "Guardian"})
		guardian.save(ignore_permissions=True)
		return guardian.name

	def find_guardian(self):
		if self.email:
			guardian = frappe.db.get_value("Guardian", {"email": self.email.strip()}, "name")
			if guardian:
				return guardian

		phone = normalize_phone(self.phone_number)
		if not phone:
			return None

		for guardian in frappe.get_all(
			"Guardian", filters={"phone": ["is", "set"]}, fields=["name", "phone"]
		):
			if normalize_phone(guardian.phone) == phone:
				return guardian.name


def normalize_phone(phone):
	# Compare the last 9 digits so +255-7XX..., 2557XX... and 07XX... match
	digits = re.sub(r"\D", "", phone or "")
	return digits[-9:] if len(digits) >= 9 else None
