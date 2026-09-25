import frappe

from smart_school.marks_alerts import DEFAULTS


def execute():
	"""Single doctypes do not get field defaults on an existing site; fill the marks alert settings once."""
	settings = frappe.get_single("Smart School Settings")
	for fieldname, value in DEFAULTS.items():
		if not settings.get(fieldname):
			settings.set(fieldname, value)
	settings.save(ignore_permissions=True)
