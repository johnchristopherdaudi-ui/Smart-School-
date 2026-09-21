import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to view this page"), frappe.PermissionError)

    guardian_name = frappe.db.get_value("Guardian", {"user": frappe.session.user}, "name")
    if not guardian_name:
        frappe.throw(_("No guardian profile linked to this account"))

    guardian = frappe.get_doc("Guardian", guardian_name)

    children = [frappe.get_doc("Student", row.student) for row in guardian.students]
    if not children:
        frappe.throw(_("No children linked to this account"))

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

    context.guardian = guardian
    context.children = children
    context.selected_student = selected_student
    context.results = results
    context.no_cache = 1
