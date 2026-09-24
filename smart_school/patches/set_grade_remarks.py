import frappe

from smart_school.patches.seed_grading_tables import GRADES


def execute():
    """Report cards show a remark per grade; fill the provisional remarks where none is set yet."""
    remarks = {grade: remark for grade, *_, remark in GRADES}
    for row in frappe.get_all("Grading System", fields=["name", "grade", "remark"]):
        if not row.remark and row.grade in remarks:
            frappe.db.set_value("Grading System", row.name, "remark", remarks[row.grade], update_modified=False)
