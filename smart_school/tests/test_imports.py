"""#1 marks import: role and assignment checks, per-row errors, BOM, subject codes, admission numbers."""

import frappe

from smart_school.tests.factory import (
	PARENT_1,
	TEACHER_1,
	SchoolTestCase,
	add_result,
	as_user,
	enforce_roles,
	call,
	make_exam,
	make_student,
)

API = "smart_school.api."


def make_file(name, text):
	return (
		frappe.get_doc(
			{"doctype": "File", "file_name": name, "is_private": 1, "content": text.encode("utf-8")}
		)
		.insert(ignore_permissions=True)
		.file_url
	)


class TestMarksImport(SchoolTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.exam = make_exam("_Test Import Exam", "_Test T2", "_Test FORM 1", max_marks=50)

	def test_parent_refused(self):
		with as_user(PARENT_1), enforce_roles():
			self.assertRaises(
				frappe.PermissionError,
				call,
				API + "bulk_create_exam_results",
				exam=self.exam,
				subject="_T MATH",
				entries=[{"student": self.s["a"], "marks": 40}],
			)

	def test_unassigned_teacher_refused(self):
		with as_user(TEACHER_1):  # teaches MATH and ENGLISH only
			self.assertRaises(
				frappe.PermissionError,
				call,
				API + "bulk_create_exam_results",
				exam=self.exam,
				subject="_T PHYSICS",
				entries=[{"student": self.s["a"], "marks": 40}],
			)

	def test_csv_with_bom_ids_names_and_row_errors(self):
		with as_user(TEACHER_1):
			url = make_file(
				"_test_marks.csv",
				"﻿Admission Number,Marks\n"
				f"{self.s['a']},45\n_Test Student B,30\nNobody Here,20\n{self.s['c']},abc\n{self.s['d']},60\n",
			)
			summary = call(API + "import_marks_from_csv", file_url=url, exam=self.exam, subject="_T ENGLISH")
			again = call(API + "import_marks_from_csv", file_url=url, exam=self.exam, subject="_T ENGLISH")
		self.assertEqual(summary["created"], 2)
		self.assertEqual(len(summary["errors"]), 3)  # unknown student, not a number, 60 > 50
		self.assertTrue(any("between 0 and 50" in e for e in summary["errors"]))
		self.assertEqual(again["skipped"], 2)  # already entered
		teacher = frappe.db.get_value(
			"Exam Result", {"exam": self.exam, "student": self.s["a"], "subject": "_T ENGLISH"}, "teacher"
		)
		self.assertEqual(teacher, self.school.teacher_1)

	def test_wide_csv_by_code_and_name(self):
		code = frappe.db.get_value("Subject", "_T MATH", "subject_code")
		with as_user(TEACHER_1):
			url = make_file(
				"_test_wide.csv", f"Student,{code},_t english,_T PHYSICS,NOSUCH\n{self.s['c']},40,35,20,10\n"
			)
			summary = call(API + "import_wide_format_csv", file_url=url, exam=self.exam)
		self.assertEqual(summary["created"], 2)  # MATH by code, ENGLISH by name (any case)
		self.assertEqual(len(summary["errors"]), 2)  # PHYSICS not assigned, NOSUCH unknown

	def test_ambiguous_name_needs_admission_number(self):
		frappe.set_user("Administrator")
		make_student("_Test Twin", "_Test FORM 1", "Male")
		frappe.get_doc(
			{
				"doctype": "Student",
				"full_name": "_Test Twin",
				"current_class": "_Test FORM 1",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		with as_user(TEACHER_1):
			summary = call(
				API + "bulk_create_exam_results",
				exam=self.exam,
				subject="_T MATH",
				entries=[{"student": "_Test Twin", "marks": 30}],
			)
		self.assertEqual(summary["created"], 0)
		self.assertIn("share this name", summary["errors"][0])

	def test_student_of_another_class_rejected(self):
		exam = make_exam("_Test Import Exam", "_Test T2", "_Test FORM 2")
		self.assertRaises(frappe.ValidationError, add_result, self.s["a"], exam, "_T MATH", 40)
