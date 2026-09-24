import frappe

MODULE = "AN INTERGRATED ACADEMIC MANAGEMENT SYSTEM"


def execute():
	"""Parents read data only through the portal, and admissions come in through the Web Form.
	Custom DocPerm rows override the doctype JSON, so drop Parent / Guest rows there too."""
	doctypes = frappe.get_all("DocType", filters={"module": MODULE}, pluck="name")
	if not doctypes:
		return

	frappe.db.delete(
		"Custom DocPerm",
		{"parent": ["in", doctypes], "role": ["in", ["Parent", "Guest"]]},
	)

	for doctype in doctypes:
		frappe.clear_cache(doctype=doctype)
