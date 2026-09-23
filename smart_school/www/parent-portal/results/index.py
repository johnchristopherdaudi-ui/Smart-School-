import frappe
from smart_school.portal_utils import get_logged_in_guardian, get_children, get_notifications, get_performance_insight

def get_context(context):
    guardian = get_logged_in_guardian()
    children = get_children(guardian)
    if not children:
        frappe.throw("No children linked to this account")

    selected_id = frappe.form_dict.get("student") or children[0].name
    selected_student = next((c for c in children if c.name == selected_id), children[0])

    results = frappe.get_all(
        "Student Term Result",
        filters={"student": selected_student.name},
        fields=["term", "average", "division", "division_display", "total_points"],
        order_by="term"
    )

    for r in results:
        term_doc = frappe.get_cached_doc("Term", r.term)
        r.term_name = term_doc.term_name
        r.subjects = frappe.get_all(
            "Exam Result",
            filters={"student": selected_student.name, "exam": ["in", frappe.get_all("Exam", filters={"term": r.term}, pluck="name")]},
            fields=["subject", "marks", "grade"]
        )

    chart_labels = [r.term_name for r in results]
    chart_values = [r.average or 0 for r in results]

    insight = get_performance_insight(selected_student.current_class)

    context.guardian = guardian
    context.children = children
    context.selected_student = selected_student
    context.results = results
    context.chart_labels = frappe.as_json(chart_labels)
    context.chart_values = frappe.as_json(chart_values)
    context.insight = insight
    notif_data = get_notifications(guardian, children)
    context.notifications = notif_data["items"]
    context.unseen_count = notif_data["unseen_count"]
    context.no_cache = 1
