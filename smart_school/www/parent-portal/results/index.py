from urllib.parse import urlencode

import frappe
from smart_school.results import get_portal_results
from smart_school.portal_utils import (
	get_portal_guardian,
	get_children,
	get_notifications,
	get_performance_insight,
)


def get_context(context):
	guardian = get_portal_guardian()
	children = get_children(guardian)
	if not children:
		frappe.throw("No children linked to this account")

	selected_id = frappe.form_dict.get("student") or children[0].name
	selected_student = next((c for c in children if c.name == selected_id), children[0])

	# Exams zilizochapishwa tu; muhtasari wa term pale Exams zote za term zimechapishwa
	results = get_portal_results(selected_student.name)
	with_summary = [r for r in results if r.summary]
	for r in with_summary:
		r.report_card_url = "/api/method/smart_school.report_card.download_report_card?" + urlencode(
			{"student": selected_student.name, "term": r.term}
		)

	chart_labels = [r.term_name for r in with_summary]
	chart_values = [r.summary.average for r in with_summary]

	insight = get_performance_insight(selected_student.current_class)

	context.guardian = guardian
	context.children = children
	context.selected_student = selected_student
	context.results = results
	context.chart_labels = chart_labels
	context.chart_values = chart_values
	context.insight = insight
	notif_data = get_notifications(guardian, children)
	context.notifications = notif_data["items"]
	context.unseen_count = notif_data["unseen_count"]
	context.no_cache = 1
