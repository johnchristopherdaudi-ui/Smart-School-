"""Setup for a fresh site. Patches do not run on install (they are only marked as done), so the data
the app needs from day one is created here."""

import frappe

STAFF_ROLES = ("Headmaster", "Teacher", "Accountant", "Parent")


def after_install():
    create_roles()

    # Provisional O-level tables (D3) with grade remarks, and the risk score defaults
    from smart_school.patches import seed_grading_tables, set_grade_remarks, set_risk_score_defaults

    seed_grading_tables.execute()
    set_grade_remarks.execute()
    set_risk_score_defaults.execute()

    frappe.db.add_unique("Student Term Result", ["student", "term"], constraint_name="unique_student_term")
    frappe.db.commit()


def create_roles():
    """Roles used by the app. Parent is portal-only (no desk access), so guardians stay Website Users."""
    for role in STAFF_ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 0 if role == "Parent" else 1}).insert(
                ignore_permissions=True
            )
    if frappe.db.get_value("Role", "Parent", "desk_access"):
        frappe.db.set_value("Role", "Parent", "desk_access", 0)
