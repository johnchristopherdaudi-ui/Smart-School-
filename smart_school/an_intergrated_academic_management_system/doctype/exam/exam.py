# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class Exam(Document):
	def validate(self):
		if flt(self.max_marks) <= 0:
			frappe.throw("Max Marks must be greater than 0")
		if self.weight and not 0 < flt(self.weight) <= 100:
			frappe.throw("Weight must be between 0 and 100")
