import frappe


def execute():
	"""Payment Gateway Log now stores the term, and the provider option is spelled "M-Pesa" like the portal."""
	frappe.db.set_value(
		"Payment Gateway Log", {"provider": "M-pesa"}, "provider", "M-Pesa", update_modified=False
	)

	logs = frappe.get_all(
		"Payment Gateway Log",
		filters={"term": ["is", "not set"], "fee_payment": ["is", "set"]},
		fields=["name", "fee_payment"],
	)
	for log in logs:
		term = frappe.db.get_value("Fee Payment", log.fee_payment, "term")
		frappe.db.set_value("Payment Gateway Log", log.name, "term", term, update_modified=False)
