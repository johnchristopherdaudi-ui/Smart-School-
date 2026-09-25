# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today

NO_RISK = {"risk_score": 0, "risk_level": None, "risk_breakdown": None, "risk_updated_on": None}


class Student(Document):
	def validate(self):
		self.set_exit_date()

	def set_exit_date(self):
		"""exit_date is the day the student left: filled when the status leaves Active (it can be corrected),
		cleared when the student is Active again. Students who left get no risk prediction."""
		if self.status == "Active":
			self.exit_date = None
			return

		if not self.exit_date:
			self.exit_date = today()
		if self.admission_date and getdate(self.exit_date) < getdate(self.admission_date):
			frappe.throw("Exit Date cannot be before the Admission Date")
		self.update(NO_RISK)
