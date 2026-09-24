# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

COMPUTED_FIELDS = (
	"student",
	"term",
	"class",
	"academic_year",
	"average",
	"division",
	"division_display",
	"total_points",
	"subjects_count",
)
FULL_ACCESS_ROLES = ("Headmaster", "System Manager")


class StudentTermResult(Document):
	def validate(self):
		other = frappe.db.get_value(
			"Student Term Result",
			{"student": self.student, "term": self.term, "name": ["!=", self.name]},
			"name",
		)
		if other:
			frappe.throw(f"{other} already holds the result of {self.student} for {self.term}")

		if not self.flags.recompute and not self.is_new():
			self.validate_manual_edit()

	def validate_manual_edit(self):
		"""Results come from the result engine; people may only write the comments, each by its owner."""
		changed = [f for f in COMPUTED_FIELDS if self.has_value_changed(f)]
		if changed:
			frappe.throw(f"{', '.join(changed)} are computed from the exam results and cannot be edited")

		roles = set(frappe.get_roles())
		if roles & set(FULL_ACCESS_ROLES):
			return

		if self.has_value_changed("headmaster_comment"):
			frappe.throw("Only the Headmaster can write the headmaster's comment", frappe.PermissionError)

		if self.has_value_changed("class_teacher_comment"):
			class_teacher = frappe.db.get_value("Class", self.get("class"), "class_teacher")
			user_teacher = frappe.db.get_value("Teacher", {"user": frappe.session.user}, "name")
			if not class_teacher or class_teacher != user_teacher:
				frappe.throw(
					f"Only the class teacher of {self.get('class')} can write this comment",
					frappe.PermissionError,
				)
