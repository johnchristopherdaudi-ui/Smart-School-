# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

AUTO_RESOLVED = "Auto-resolved"
REVIEWED = ("Reviewed-OK", "Corrected")


class MarksAlert(Document):
	def validate(self):
		from smart_school.marks_alerts import INTEGRITY_TYPES

		self.title = " - ".join(filter(None, [self.alert_type, self.subject, self.student_name]))

		if self.status == AUTO_RESOLVED and self.alert_type in INTEGRITY_TYPES:
			frappe.throw(
				f"A {self.alert_type} alert is never resolved automatically; a person must review it"
			)

		if self.is_new() or not self.has_value_changed("status"):
			return
		if self.flags.from_checks:
			return
		if self.status == AUTO_RESOLVED:
			frappe.throw("Only the marks checks set Auto-resolved; choose Reviewed-OK or Corrected")

		if self.status in REVIEWED:
			self.reviewer = frappe.session.user
			self.reviewed_on = now_datetime()
		else:
			self.reviewer = None
			self.reviewed_on = None
