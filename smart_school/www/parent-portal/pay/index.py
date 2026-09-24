import frappe
from smart_school.fees import get_term_outstanding
from smart_school.portal_utils import (
	assert_demo_payments_enabled,
	get_children,
	get_portal_guardian,
	get_payment_providers,
)


def get_context(context):
	guardian = get_portal_guardian()
	assert_demo_payments_enabled()
	children = get_children(guardian)

	student_id = frappe.form_dict.get("student")
	term = frappe.form_dict.get("term")

	allowed_ids = [c.name for c in children]
	if student_id not in allowed_ids:
		frappe.throw("Huna ruhusa ya kulipia mwanafunzi huyu")

	if not term or not frappe.db.exists("Term", term):
		frappe.throw("Muhula (term) haupo")

	selected_student = next(c for c in children if c.name == student_id)
	term_name = frappe.get_cached_value("Term", term, "term_name")

	# Deni linahesabiwa server-side; mzazi anaweza kulipa kiasi chochote hadi deni hili
	amount = get_term_outstanding(student_id, term)
	if amount <= 0:
		frappe.throw("Hakuna deni lililobaki kwa muhula huu")

	context.guardian = guardian
	context.selected_student = selected_student
	context.term = term
	context.term_name = term_name
	context.amount = amount
	context.providers = get_payment_providers()
	context.hide_portal_nav = 1
	context.no_cache = 1
