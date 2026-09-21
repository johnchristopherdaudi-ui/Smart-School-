import frappe

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect=/results"
        raise frappe.Redirect

    parent_email = frappe.session.user
    frappe.flags.ignore_permissions = True

    try:
        # 1. Fetch Guardian ID by email
        guardian_name = frappe.db.get_value("Guardian", {"email": parent_email}, "name")
        if not guardian_name:
            context.error = f"No guardian account found matching email: {parent_email}"
            return context

        # 2. Get linked student from Guardian document
        guardian_doc = frappe.get_doc("Guardian", guardian_name)
        
        student_id = None
        student_name = None

        if hasattr(guardian_doc, "students") and guardian_doc.students:
            row = guardian_doc.students[0]
            student_id = getattr(row, "student", None)
            student_name = getattr(row, "student_name", None)

        if not student_id and not student_name:
            context.error = "No student record linked to your guardian account."
            return context

        # 3. Resolve Student Document ID
        if not student_id and student_name:
            student_id = frappe.db.get_value("Student", {"student_name": student_name}, "name")

        if not student_id or not frappe.db.exists("Student", student_id):
            context.error = "Linked student record could not be found in the system."
            return context

        # 4. Fetch Student Document
        context.student = frappe.get_doc("Student", student_id)

        # 5. Group Exam Results by Exam Title using actual database fields
        context.results = frappe.db.sql("""
            SELECT 
                exam AS examname,
                COUNT(subject) AS total_subjects,
                GROUP_CONCAT(CONCAT(subject, " - ", marks, " (", IFNULL(grade, '-'), ")") SEPARATOR " | ") AS detailed_subjects
            FROM `tabExam Result`
            WHERE student = %s
            GROUP BY exam
            ORDER BY creation DESC
        """, (context.student.name,), as_dict=True)

    finally:
        frappe.flags.ignore_permissions = False