import frappe


def execute():
	"""Tuned on the demo school: the class average must also differ by 10 points, and a student's change needs
	a robust z above 4.5. A student z still at the old default of 3.5 moves to 4.5; one set by hand is kept."""
	settings = frappe.get_single("Smart School Settings")
	if not settings.alert_class_min_diff:
		settings.alert_class_min_diff = 10
	if settings.alert_student_z in (None, 0, 3.5):
		settings.alert_student_z = 4.5
	settings.save(ignore_permissions=True)
