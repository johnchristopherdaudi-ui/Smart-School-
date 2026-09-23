from urllib.parse import urlencode

import frappe
from smart_school.portal_utils import assert_demo_payments_enabled, get_logged_in_guardian

def get_context(context):
    guardian = get_logged_in_guardian()
    assert_demo_payments_enabled()

    reference = frappe.form_dict.get("ref")
    log_name = frappe.db.get_value("Payment Gateway Log", {"transaction_reference": reference}, "name")
    if not reference or not log_name:
        frappe.throw("Muamala haupo")

    log = frappe.get_doc("Payment Gateway Log", log_name)

    # Hakikisha huyu guardian ndiye mwenye ruhusa ya log hii
    allowed_students = [row.student for row in guardian.students]
    if log.student not in allowed_students:
        frappe.throw("Huna ruhusa ya kufikia malipo haya")

    context.log = log
    context.reference = reference
    context.fees_url = "/parent-portal/fees?" + urlencode({"student": log.student})
    context.no_cache = 1
