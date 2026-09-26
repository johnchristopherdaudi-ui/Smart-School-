# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from smart_school.branding import make_logo_public, sync_website_settings

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
		self.validate_marks_alerts()
		make_logo_public(self)

	def validate_marks_alerts(self):
		if (self.alert_min_class_size or 0) < 3:
			frappe.throw("Marks alerts: Minimum Class Size must be at least 3")
		if (self.alert_history_min_exams or 0) < 3:
			frappe.throw("Marks alerts: History: Minimum Exams must be at least 3")
		for fieldname in ("alert_identical_share", "alert_zero_share", "alert_round_share", "alert_zero_drop_from"):
			if not 0 < (self.get(fieldname) or 0) <= 100:
				frappe.throw(f"Marks alerts: {self.meta.get_label(fieldname)} must be between 1 and 100")
		for fieldname in ("alert_class_z", "alert_student_z"):
			if (self.get(fieldname) or 0) <= 0:
				frappe.throw(f"Marks alerts: {self.meta.get_label(fieldname)} must be greater than 0")

	def on_update(self):
		sync_website_settings(self)


def demo_payments_enabled():
	return bool(frappe.db.get_single_value("Smart School Settings", "enable_demo_payments"))
