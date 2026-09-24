import frappe


def execute():
    """Fee Payment is now submittable. Existing payments are real money already received, so submit them
    in the order they were recorded (keeping their names). FeePayment.on_submit skips notifications in patches."""
    for name in frappe.get_all("Fee Payment", filters={"docstatus": 0}, pluck="name", order_by="creation asc"):
        doc = frappe.get_doc("Fee Payment", name)
        doc.flags.ignore_permissions = True
        doc.submit()
