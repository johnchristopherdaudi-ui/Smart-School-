import frappe


def get_current_teacher():
    teacher = frappe.get_value("Teacher", {"user": frappe.session.user}, "name")
    return teacher


@frappe.whitelist()
def bulk_create_exam_results(exam, subject, entries):
    import json

    if isinstance(entries, str):
        entries = json.loads(entries)

    teacher = get_current_teacher()

    created = 0
    skipped = 0

    for entry in entries:
        student = entry.get("student")
        marks = entry.get("marks")

        existing = frappe.get_all(
            "Exam Result",
            filters={"student": student, "subject": subject, "exam": exam}
        )

        if existing:
            skipped += 1
            continue

        doc = frappe.get_doc({
            "doctype": "Exam Result",
            "student": student,
            "subject": subject,
            "exam": exam,
            "marks": marks,
            "teacher": teacher
        })
        doc.insert(ignore_permissions=True)
        doc.submit()

        created += 1

    return {"created": created, "skipped": skipped}


@frappe.whitelist()
def import_marks_from_csv(file_url, exam, subject):
    import csv

    class_name = frappe.get_value("Exam", exam, "class")
    teacher = get_current_teacher()

    file_doc = frappe.get_all("File", filters={"file_url": file_url}, fields=["name"])

    if not file_doc:
        frappe.throw(f"File not found for URL: {file_url}")

    file_doc = frappe.get_doc("File", file_doc[0].name)
    file_path = file_doc.get_full_path()

    created = 0
    skipped = 0
    not_found = []

    with open(file_path, "r") as f:
        reader = csv.reader(f)
        first_row = True

        for row in reader:
            if first_row:
                first_row = False
                if row[0].strip().lower() in ["full name", "name", "student"]:
                    continue

            if len(row) < 2:
                continue

            student_name = row[0].strip()
            marks_value = row[1].strip()

            if not student_name or not marks_value:
                continue

            try:
                marks = float(marks_value)
            except ValueError:
                skipped += 1
                continue

            student = frappe.get_all(
                "Student",
                filters={"full_name": student_name, "current_class": class_name},
                fields=["name"]
            )

            if not student:
                not_found.append(student_name)
                skipped += 1
                continue

            student_id = student[0].name

            existing = frappe.get_all(
                "Exam Result",
                filters={"student": student_id, "subject": subject, "exam": exam}
            )

            if existing:
                skipped += 1
                continue

            doc = frappe.get_doc({
                "doctype": "Exam Result",
                "student": student_id,
                "subject": subject,
                "exam": exam,
                "marks": marks,
                "teacher": teacher
            })
            doc.insert(ignore_permissions=True)
            doc.submit()

            created += 1

    return {"created": created, "skipped": skipped, "not_found": not_found}


@frappe.whitelist()
def import_wide_format_csv(file_url, exam, class_name):
    teacher = get_current_teacher()

    file_doc = frappe.get_all("File", filters={"file_url": file_url}, fields=["name"])

    if not file_doc:
        frappe.throw(f"File not found for URL: {file_url}")

    file_doc = frappe.get_doc("File", file_doc[0].name)
    file_path = file_doc.get_full_path()

    if file_path.lower().endswith(".xlsx"):
        rows = read_excel_rows(file_path)
    else:
        rows = read_csv_rows(file_path)

    if not rows:
        frappe.throw("The file appears to be empty.")

    header = rows[0]
    subject_columns = header[1:]

    created = 0
    skipped = 0
    not_found = []

    for row in rows[1:]:
        if not row or not str(row[0]).strip():
            continue

        student_name = str(row[0]).strip()

        student = frappe.get_all(
            "Student",
            filters={"full_name": student_name, "current_class": class_name},
            fields=["name"]
        )

        if not student:
            not_found.append(student_name)
            continue

        student_id = student[0].name

        for i, subject_name in enumerate(subject_columns):
            if i + 1 >= len(row):
                continue

            marks_value = row[i + 1]

            if marks_value is None or str(marks_value).strip() == "":
                continue

            try:
                marks = float(marks_value)
            except (ValueError, TypeError):
                skipped += 1
                continue

            existing = frappe.get_all(
                "Exam Result",
                filters={"student": student_id, "subject": subject_name, "exam": exam}
            )

            if existing:
                skipped += 1
                continue

            doc = frappe.get_doc({
                "doctype": "Exam Result",
                "student": student_id,
                "subject": subject_name,
                "exam": exam,
                "marks": marks,
                "teacher": teacher
            })
            doc.insert(ignore_permissions=True)
            doc.submit()

            created += 1

    return {"created": created, "skipped": skipped, "not_found": not_found}


def read_csv_rows(file_path):
    import csv

    with open(file_path, "r") as f:
        reader = csv.reader(f)
        return [row for row in reader]


def read_excel_rows(file_path):
    import openpyxl

    workbook = openpyxl.load_workbook(file_path, data_only=True)
    sheet = workbook.active

    rows = []
    for row in sheet.iter_rows(values_only=True):
        rows.append(list(row))

    return rows