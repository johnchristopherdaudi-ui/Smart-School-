# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint

from smart_school.tasks import ensure_academic_record

PROMOTER_ROLES = ("Headmaster", "System Manager")


class StudentPromotionTool(Document):
	def get_next_class(self):
		"""The class one level up, or None when from_class is the top class (students graduate)."""
		level = cint(frappe.db.get_value("Class", self.from_class, "level"))
		next_classes = frappe.get_all("Class", filters={"level": level + 1}, pluck="name")
		if len(next_classes) > 1:
			frappe.throw(f"More than one class has level {level + 1}: {', '.join(next_classes)}")
		return next_classes[0] if next_classes else None

	@frappe.whitelist()
	def get_students(self):
		frappe.only_for(PROMOTER_ROLES)
		next_class = self.get_next_class()
		self.to_class = next_class or "Graduated"

		self.set("students", [])
		for student in frappe.get_all(
			"Student",
			filters={"current_class": self.from_class, "status": "Active"},
			fields=["name", "full_name"],
			order_by="full_name asc",
		):
			last = frappe.db.sql(
				"""select str.average, str.division, str.division_display
				from `tabStudent Term Result` str join `tabTerm` t on t.name = str.term
				where str.student = %s and t.academic_year = %s
				order by t.start_date desc limit 1""",
				(student.name, self.academic_year),
				as_dict=True,
			)
			last = last[0] if last else frappe._dict()
			self.append(
				"students",
				{
					"student": student.name,
					"student_name": student.full_name,
					"final_average": last.get("average"),
					"final_division": last.get("division_display") or last.get("division"),
					"action": "Promote",
				},
			)
		return len(self.students)

	@frappe.whitelist()
	def promote(self):
		"""Record the finished year, then move students up (top class: Graduated). Repeaters stay."""
		frappe.only_for(PROMOTER_ROLES)
		if not self.students:
			frappe.throw("Get Students first")

		next_class = self.get_next_class()
		counts = {"promoted": 0, "graduated": 0, "repeating": 0, "skipped": 0}
		for row in self.students:
			student = frappe.get_doc("Student", row.student)
			if student.current_class != self.from_class or student.status != "Active":
				counts["skipped"] += 1  # already promoted or no longer active
				continue

			ensure_academic_record(student.name, self.academic_year, self.from_class)

			if row.action == "Repeat":
				counts["repeating"] += 1
				continue

			if next_class:
				student.current_class = next_class
				student.current_section = None
				counts["promoted"] += 1
			else:
				student.status = "Graduated"
				counts["graduated"] += 1
			student.save(ignore_permissions=True)

		self.set("students", [])
		self.save(ignore_permissions=True)
		return counts
