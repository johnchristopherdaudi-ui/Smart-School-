# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SmartSchoolSettings(Document):
	pass


def demo_payments_enabled():
	return bool(frappe.db.get_single_value("Smart School Settings", "enable_demo_payments"))
