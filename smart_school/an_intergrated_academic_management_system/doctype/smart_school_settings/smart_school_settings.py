# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

RISK_WEIGHTS = (
	"risk_weight_attendance",
	"risk_weight_discipline",
	"risk_weight_low_average",
	"risk_weight_failed_subjects",
	"risk_weight_decline",
)


class SmartSchoolSettings(Document):
	def validate(self):
		total = sum(self.get(f) or 0 for f in RISK_WEIGHTS)
		if total != 100:
			frappe.throw(f"Risk score weights must add up to 100 (now {total})")
		if not 0 < (self.risk_medium_from or 0) < (self.risk_high_from or 0) <= 100:
			frappe.throw("Risk levels must satisfy 0 < Medium From < High From <= 100")
		if not 0 < (self.risk_average_threshold or 0) <= 100:
			frappe.throw("Low Average Below must be between 1 and 100")


def demo_payments_enabled():
	return bool(frappe.db.get_single_value("Smart School Settings", "enable_demo_payments"))
