import frappe

DEFAULTS = {
	"risk_weight_attendance": 25,
	"risk_weight_discipline": 20,
	"risk_weight_low_average": 25,
	"risk_weight_failed_subjects": 15,
	"risk_weight_decline": 15,
	"risk_average_threshold": 45,
	"risk_medium_from": 30,
	"risk_high_from": 60,
}


def execute():
	"""Single doctypes do not get field defaults on an existing site; fill the risk settings once."""
	settings = frappe.get_single("Smart School Settings")
	for fieldname, value in DEFAULTS.items():
		if not settings.get(fieldname):
			settings.set(fieldname, value)
	settings.save(ignore_permissions=True)
