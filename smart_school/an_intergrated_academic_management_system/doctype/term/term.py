# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class Term(Document):
	def validate(self):
		if getdate(self.start_date) >= getdate(self.end_date):
			frappe.throw("Start Date must be before End Date")

		year_start, year_end = frappe.db.get_value("Academic Year", self.academic_year, ["start_date", "end_date"])
		if getdate(self.start_date) < getdate(year_start) or getdate(self.end_date) > getdate(year_end):
			frappe.throw(f"The term must lie within the academic year {self.academic_year} ({year_start} to {year_end})")

		overlap = frappe.get_all(
			"Term",
			filters={
				"academic_year": self.academic_year,
				"name": ["!=", self.name],
				"start_date": ["<=", self.end_date],
				"end_date": [">=", self.start_date],
			},
			pluck="name",
		)
		if overlap:
			frappe.throw(f"This term overlaps with {', '.join(overlap)}")
