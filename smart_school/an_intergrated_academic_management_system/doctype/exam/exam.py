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
		self.validate_weights()

	def validate_weights(self):
		"""Exams of one class in one term are either all weighted or all unweighted, never above 100 in total.
		The exact total of 100 is checked when results are published (exams are created one at a time)."""
		others = frappe.get_all(
			"Exam",
			filters={"class": self.get("class"), "term": self.term, "name": ["!=", self.name]},
			fields=["name", "weight"],
		)
		weights = [flt(e.weight) for e in others] + [flt(self.weight)]
		if any(weights) and not all(weights):
			frappe.throw(
				f"Exams of {self.get('class')} in {self.term} must all have a weight or all have none "
				f"({', '.join(e.name for e in others)})"
			)
		if sum(weights) > 100:
			frappe.throw(
				f"Weights of {self.get('class')} exams in {self.term} add up to {sum(weights):g}, more than 100"
			)
