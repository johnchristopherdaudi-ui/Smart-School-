"""#24 report card: data, PDF, class printing, and the parent download (own child, published term only)."""

import frappe

from smart_school import report_card
from smart_school.tests.factory import (
	HEADMASTER,
	PARENT_1,
	PARENT_2,
	SUBJECTS,
	TEACHER_1,
	SchoolTestCase,
	add_result,
	as_user,
	enforce_roles,
	call,
	make_exam,
	render,
)

DOWNLOAD = "smart_school.report_card.download_report_card"


class TestReportCard(SchoolTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.mid = make_exam("_Test RC Mid", "_Test T2", "_Test FORM 1", max_marks=50, weight=40, published=1)
		cls.final = make_exam("_Test RC Final", "_Test T2", "_Test FORM 1", weight=60, published=1)
		for key, mark in (("a", 80), ("b", 60)):
			for subject in SUBJECTS[:7]:
				add_result(cls.s[key], cls.mid, subject, mark / 2)
				add_result(cls.s[key], cls.final, subject, mark)
		frappe.get_doc(
			{
				"doctype": "Attendance",
				"student": cls.s["a"],
				"status": "Absent",
				"date": frappe.db.get_value("Term", "_Test T2", "start_date"),
			}
		).insert(ignore_permissions=True)
		cls.result = frappe.db.get_value(
			"Student Term Result", {"student": cls.s["a"], "term": "_Test T2"}, "name"
		)

	def test_card_data(self):
		rc = report_card.get_report_card_data(self.result)
		self.assertEqual([e.exam_name for e in rc.exams], ["_Test RC Mid", "_Test RC Final"])
		math = next(s for s in rc.subjects if s.subject == "_T MATH")
		self.assertEqual(
			(math.exam_marks, math.score, math.grade, math.remark, math.points),
			([40, 80], 80, "A", "Excellent", 1),
		)
		self.assertEqual(rc.position_text, "Position 1 out of 2")
		self.assertEqual((rc.attendance.days, rc.attendance.absent), (1, 1))
		next_term = frappe.db.get_value("Term", "_Test T3", "start_date")
		self.assertEqual(rc.next_term_opens, frappe.utils.formatdate(next_term, "dd MMMM yyyy"))

	def test_print_format_and_pdf(self):
		html = frappe.get_print("Student Term Result", self.result, "Report Card")
		for text in ("STUDENT REPORT CARD", "Position 1 out of 2", "Next term begins", "_Test Student A"):
			self.assertIn(text, html)
		self.assertTrue(report_card.render_pdf(self.result).startswith(b"%PDF"))

	def test_class_printing_headmaster_only(self):
		with as_user(HEADMASTER):
			names = report_card.get_class_report_cards("_Test FORM 1", "_Test T2")
		self.assertEqual(names[0], self.result)  # merit order
		with as_user(TEACHER_1), enforce_roles():
			self.assertRaises(
				frappe.PermissionError, report_card.get_class_report_cards, "_Test FORM 1", "_Test T2"
			)

	def test_parent_download(self):
		with as_user(PARENT_1):
			frappe.local.response = frappe._dict()
			call(DOWNLOAD, student=self.s["a"], term="_Test T2")
			self.assertEqual(frappe.local.response.type, "pdf")
			self.assertTrue(frappe.local.response.filecontent.startswith(b"%PDF"))
			self.assertIn("term=_Test+T2", render("parent-portal/results", student=self.s["a"])[1])
		with as_user(PARENT_2):
			self.assertRaises(frappe.PermissionError, call, DOWNLOAD, student=self.s["a"], term="_Test T2")

	def test_download_needs_every_exam_published(self):
		frappe.db.set_value("Exam", self.final, "results_published", 0)
		with as_user(PARENT_1):
			self.assertRaises(frappe.PermissionError, call, DOWNLOAD, student=self.s["a"], term="_Test T2")
			self.assertNotIn("term=_Test+T2", render("parent-portal/results", student=self.s["a"])[1])
		frappe.db.set_value("Exam", self.final, "results_published", 1)
