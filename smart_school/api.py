import csv
import json

import frappe

MARKS_ENTRY_ROLES = ("Teacher", "Headmaster", "System Manager")
MARKS_ADMIN_ROLES = ("Headmaster", "System Manager")
STUDENT_HEADERS = ("student", "name", "full name", "admission number", "admission no")


class ImportRowError(Exception):
	pass


def get_current_teacher():
	return frappe.get_value("Teacher", {"user": frappe.session.user}, "name")


def _assert_can_enter_marks(exam):
	"""Return (exam class, teacher). teacher is None for Headmaster / System Manager,
	who may enter any subject; Teachers are limited to their Teacher Subject Assignments."""
	frappe.only_for(MARKS_ENTRY_ROLES)

	exam_class = frappe.get_value("Exam", exam, "class")
	if not exam_class:
		frappe.throw(f"Exam {exam} not found", frappe.DoesNotExistError)

	if set(MARKS_ADMIN_ROLES) & set(frappe.get_roles()):
		return exam_class, None

	teacher = get_current_teacher()
	if not teacher:
		frappe.throw("Your user is not linked to a Teacher record", frappe.PermissionError)
	return exam_class, teacher


def _subject_error(exam_class, subject, teacher):
	if not frappe.db.exists("Class Subject Mapping", {"class": exam_class, "subject": subject}):
		return f"{subject} is not taught in {exam_class}"

	if teacher and not frappe.db.exists(
		"Teacher Subject Assignment",
		{"parenttype": "Teacher", "parent": teacher, "subject": subject, "class": exam_class},
	):
		return f"You are not assigned to teach {subject} in {exam_class}"


def _assert_can_enter_subject(exam_class, subject, teacher):
	error = _subject_error(exam_class, subject, teacher)
	if error:
		frappe.throw(error, frappe.PermissionError)


@frappe.whitelist()
def bulk_create_exam_results(exam, subject, entries):
	exam_class, teacher = _assert_can_enter_marks(exam)
	_assert_can_enter_subject(exam_class, subject, teacher)

	if isinstance(entries, str):
		entries = json.loads(entries)

	summary = _new_summary()
	for i, entry in enumerate(entries, start=1):
		_import_row(summary, f"Row {i}", entry.get("student"), exam, exam_class, subject, entry.get("marks"))
	return summary


@frappe.whitelist()
def import_marks_from_csv(file_url, exam, subject):
	exam_class, teacher = _assert_can_enter_marks(exam)
	_assert_can_enter_subject(exam_class, subject, teacher)

	summary = _new_summary()
	for i, row in enumerate(_read_file_rows(file_url), start=1):
		if len(row) < 2 or not _cell(row[0]):
			continue
		if i == 1 and _cell(row[0]).lower() in STUDENT_HEADERS:
			continue
		_import_row(summary, f"Row {i}", row[0], exam, exam_class, subject, row[1])
	return summary


@frappe.whitelist()
def import_wide_format_csv(file_url, exam, class_name=None):
	# class_name is kept for old callers; the class always comes from the exam
	exam_class, teacher = _assert_can_enter_marks(exam)

	rows = _read_file_rows(file_url)
	if not rows:
		frappe.throw("The file appears to be empty.")

	summary = _new_summary()
	subjects = []
	for header in rows[0][1:]:
		subject = _resolve_subject(header)
		error = _subject_error(exam_class, subject, teacher) if subject else "subject not found"
		if error and _cell(header):
			summary["errors"].append(f"Column '{_cell(header)}': {error}")
		subjects.append(None if error else subject)

	if not any(subjects):
		frappe.throw("No subject column in this file can be imported", frappe.PermissionError)

	for i, row in enumerate(rows[1:], start=2):
		if not row or not _cell(row[0]):
			continue
		for subject, marks_value in zip(subjects, row[1:]):
			if subject:
				_import_row(summary, f"Row {i}", row[0], exam, exam_class, subject, marks_value)

	return summary


def _new_summary():
	return {"created": 0, "skipped": 0, "errors": []}


def _import_row(summary, label, student_ref, exam, exam_class, subject, marks_value):
	"""Create and submit one Exam Result. Errors are collected per row instead of aborting the import."""
	if _cell(marks_value) == "":
		return

	message_count = len(frappe.local.message_log)
	frappe.db.savepoint("marks_row")
	try:
		student = _resolve_student(student_ref, exam_class)
		marks = _parse_marks(marks_value, frappe.get_cached_value("Exam", exam, "max_marks") or 100)
		if not _subject_allowed_for_student(exam_class, subject, student):
			raise ImportRowError(f"{subject} is not in this student's combination")

		if frappe.db.exists(
			"Exam Result", {"student": student, "subject": subject, "exam": exam, "docstatus": ["<", 2]}
		):
			summary["skipped"] += 1
			return

		doc = frappe.get_doc(
			{
				"doctype": "Exam Result",
				"student": student,
				"subject": subject,
				"exam": exam,
				"marks": marks,
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		summary["created"] += 1
	except (ImportRowError, frappe.ValidationError, frappe.PermissionError) as e:
		frappe.db.rollback(save_point="marks_row")
		del frappe.local.message_log[message_count:]
		summary["errors"].append(f"{label} ({_cell(student_ref)}, {subject}): {e}")


def _resolve_student(student_ref, exam_class):
	"""Match by admission number (Student ID) first, then by full name if it is unique in the class."""
	ref = _cell(student_ref)
	if not ref:
		raise ImportRowError("student is empty")

	student = frappe.db.exists("Student", {"name": ref, "current_class": exam_class})
	if student:
		return student

	matches = frappe.get_all("Student", filters={"full_name": ref, "current_class": exam_class}, pluck="name")
	if len(matches) == 1:
		return matches[0]
	if matches:
		raise ImportRowError(
			f"{len(matches)} students in {exam_class} share this name, use the admission number"
		)
	raise ImportRowError(f"student not found in {exam_class}")


def _resolve_subject(header):
	ref = _cell(header)
	if not ref:
		return None

	subject = frappe.db.exists("Subject", ref)
	if subject:
		return subject

	for fieldname in ("subject_name", "subject_code"):
		subject = frappe.db.get_value("Subject", {fieldname: ref}, "name")
		if subject:
			return subject


def _subject_allowed_for_student(exam_class, subject, student):
	combination = frappe.get_value("Student", student, "combination")
	mappings = frappe.get_all(
		"Class Subject Mapping",
		filters={"class": exam_class, "subject": subject},
		fields=["subject_scope", "combination"],
	)
	return any(m.subject_scope == "All Combinations" or m.combination == combination for m in mappings)


def _parse_marks(value, max_marks):
	try:
		marks = float(_cell(value))
	except ValueError:
		raise ImportRowError(f"marks '{_cell(value)}' is not a number")

	if not 0 <= marks <= max_marks:
		raise ImportRowError(f"marks {marks:g} must be between 0 and {max_marks:g}")
	return marks


def _cell(value):
	return "" if value is None else str(value).strip()


def _read_file_rows(file_url):
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		frappe.throw(f"File not found for URL: {file_url}")

	file_doc = frappe.get_doc("File", file_name)
	file_doc.check_permission("read")
	file_path = file_doc.get_full_path()

	if file_path.lower().endswith(".xlsx"):
		return read_excel_rows(file_path)
	return read_csv_rows(file_path)


def read_csv_rows(file_path):
	# utf-8-sig strips the BOM that Excel adds, which otherwise breaks header detection
	with open(file_path, encoding="utf-8-sig", newline="") as f:
		return list(csv.reader(f))


def read_excel_rows(file_path):
	import openpyxl

	workbook = openpyxl.load_workbook(file_path, data_only=True)
	sheet = workbook.active

	rows = []
	for row in sheet.iter_rows(values_only=True):
		rows.append(list(row))

	return rows
