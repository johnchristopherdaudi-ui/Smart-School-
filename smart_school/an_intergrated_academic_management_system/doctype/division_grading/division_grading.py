# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from smart_school.results import validate_non_overlapping_range


class DivisionGrading(Document):
	def validate(self):
		validate_non_overlapping_range(self, "minimum_points", "maximum_points", unique_fields=("division",))
