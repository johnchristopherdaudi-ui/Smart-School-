# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ClassSubjectMapping(Document):
	def validate(self):
		if self.subject_scope == "All Combinations":
			self.combination = None
		elif not self.combination:
			frappe.throw("Combination is required when the scope is Specific Combination")
		self.check_duplicate()

	def check_duplicate(self):
		existing = frappe.get_all(
			"Class Subject Mapping",
			filters={
				"class": self.get("class"),
				"subject": self.subject,
				"combination": self.combination,
				"name": ["!=", self.name],
			},
		)

		if existing:
			frappe.throw(f"Subject '{self.subject}' has already been assigned to this Class and Combination.")
