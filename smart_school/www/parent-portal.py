import frappe

no_cache = 1

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/parent-portal"
        raise frappe.Redirect

    guardian = frappe.get_value("Guardian", {"user": frappe.session.user}, "name")

    if not guardian:
        context.error_message = "No Guardian record found for this account."
        context.students = []
        context.guardian_name = ""
        return

    guardian_doc = frappe.get_doc("Guardian", guardian)

    student_links = frappe.get_all(
        "Guardian Student Link",
        filters={"parent": guardian},
        fields=["student"]
    )

    students_data = []

    for link in student_links:
        student = frappe.get_doc("Student", link.student)

        term_results = frappe.get_all(
            "Student Term Result",
            filters={"student": student.name},
            fields=["term", "average", "division_display", "total_points"],
            order_by="creation desc",
            limit_page_length=1
        )

        fee_payments = frappe.get_all(
            "Fee Payment",
            filters={"student": student.name},
            fields=["balance", "status"],
            order_by="creation desc",
            limit_page_length=1
        )

        students_data.append({
            "name": student.full_name,
            "current_class": student.current_class,
            "combination": student.combination or "N/A",
            "latest_result": term_results[0] if term_results else None,
            "latest_fee": fee_payments[0] if fee_payments else None
        })

    context.guardian_name = guardian_doc.full_name
    context.students = students_data
    context.error_message = None
