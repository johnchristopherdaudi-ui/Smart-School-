import frappe

# Provisional O-level tables (D3), to be confirmed by the academic master. They stay editable data:
# this only fills empty tables on a fresh install and never overwrites edited rows.
GRADES = [("A", 75, 100, 1), ("B", 65, 74, 2), ("C", 45, 64, 3), ("D", 30, 44, 4), ("F", 0, 29, 5)]
DIVISIONS = [("Division I", 7, 17), ("Division II", 18, 21), ("Division III", 22, 25), ("Division IV", 26, 33), ("Division 0", 34, 35)]


def execute():
    if not frappe.db.count("Grading System"):
        for grade, low, high, points in GRADES:
            frappe.get_doc({
                "doctype": "Grading System", "grade": grade, "minimum_mark": low, "maximum_mark": high, "points": points
            }).insert(set_name=f"GRADE {grade}", ignore_permissions=True)

    if not frappe.db.count("Division Grading"):
        for division, low, high in DIVISIONS:
            frappe.get_doc({
                "doctype": "Division Grading", "division": division, "minimum_points": low, "maximum_points": high
            }).insert(set_name=division, ignore_permissions=True)
