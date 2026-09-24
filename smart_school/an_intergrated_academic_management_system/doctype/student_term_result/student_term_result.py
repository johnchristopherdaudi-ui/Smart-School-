# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StudentTermResult(Document):
	def validate(self):
		other = frappe.db.get_value(
			"Student Term Result", {"student": self.student, "term": self.term, "name": ["!=", self.name]}, "name"
		)
		if other:
			frappe.throw(f"{other} already holds the result of {self.student} for {self.term}")
