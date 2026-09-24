# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class AcademicYear(Document):
	def validate(self):
		if getdate(self.start_date) >= getdate(self.end_date):
			frappe.throw("Start Date must be before End Date")

		outside = frappe.get_all(
			"Term",
			filters={"academic_year": self.name, "start_date": ["<", self.start_date]},
			pluck="name",
		) + frappe.get_all(
			"Term",
			filters={"academic_year": self.name, "end_date": [">", self.end_date]},
			pluck="name",
		)
		if outside:
			frappe.throw(f"Terms {', '.join(sorted(set(outside)))} would fall outside this academic year")
