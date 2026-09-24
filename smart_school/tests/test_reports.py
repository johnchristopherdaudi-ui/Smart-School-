"""#23 reports: ranking, subject statistics, fee defaulters, and who may run which report."""

import frappe
from frappe.desk.query_report import run

from smart_school import reports
from smart_school.tests.factory import (
	ACCOUNTANT,
	HEADMASTER,
	SUBJECTS,
	TEACHER_1,
	TEACHER_2,
	SchoolTestCase,
	add_result,
	as_user,
	enforce_roles,
	make_exam,
	pay,
)


def rows(report, **filters):
	# add_total_row appends the total as a list: keep the data rows
	return [r for r in run(report, filters=filters)["result"] if isinstance(r, dict)]


class TestReports(SchoolTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		exam = make_exam("_Test Report Exam", "_Test T2", "_Test FORM 1")
		plan = {"a": 70, "b": 60, "c": 60, "d": 50}  # averages 70, 60, 60, 50 -> positions 1, 2, 2, 4
		for key, mark in plan.items():
			for subject in SUBJECTS[:7]:
				add_result(cls.s[key], exam, subject, 20 if (key == "d" and subject == "_T MATH") else mark)
		cls.incomplete = (
			frappe.get_doc(
				{
					"doctype": "Student",
					"full_name": "_Test Six Subjects",
					"current_class": "_Test FORM 1",
					"status": "Active",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		for subject in SUBJECTS[:6]:
			add_result(cls.incomplete, exam, subject, 90)

	def test_merit_list_ties_and_incomplete_apart(self):
		with as_user(HEADMASTER):
			data = rows("Class Merit List", **{"class": "_Test FORM 1", "term": "_Test T2"})
		ranked = [(r["student"], r["position"]) for r in data if r["position"]]
		self.assertEqual([p for _, p in ranked], [1, 2, 2, 4])
		self.assertEqual(ranked[0][0], self.s["a"])
		self.assertEqual(data[-1]["student"], self.incomplete)
		self.assertIsNone(data[-1]["position"])

	def test_subject_performance(self):
		with as_user(HEADMASTER):
			data = rows("Subject Performance", term="_Test T2", **{"class": "_Test FORM 1"})
		math = next(r for r in data if r["subject"] == "_T MATH")
		# 70, 60, 60, 20, 90 -> mean 60, one F out of five
		self.assertEqual((math["students"], math["mean"], math["pass_rate"], math["f"]), (5, 60, 80, 1))
		self.assertEqual(math["teacher"], self.school.teacher_1)

	def test_teacher_limited_to_assigned_classes_and_subjects(self):
		with as_user(TEACHER_1):
			subjects = {
				r["subject"]
				for r in rows("Subject Performance", term="_Test T2", **{"class": "_Test FORM 1"})
			}
			self.assertEqual(subjects, {"_T MATH", "_T ENGLISH"})
			self.assertRaises(
				frappe.PermissionError,
				rows,
				"Class Merit List",
				**{"class": "_Test FORM 2", "term": "_Test T2"},
			)
			self.assertRaises(frappe.PermissionError, rows, "Fee Collection and Defaulters")
			with enforce_roles():
				self.assertRaises(frappe.PermissionError, reports.get_outstanding_fees)
			classes = {r["class"] for r in rows("My Classes", term="_Test T2")}
			self.assertEqual(classes, {"_Test FORM 1"})

	def test_accountant_limited_to_fee_reports(self):
		with as_user(ACCOUNTANT):
			self.assertRaises(
				frappe.PermissionError,
				rows,
				"Class Merit List",
				**{"class": "_Test FORM 1", "term": "_Test T2"},
			)
			self.assertRaises(frappe.PermissionError, rows, "At-Risk Students")
			self.assertEqual(reports.get_outstanding_fees()["fieldtype"], "Currency")

	def test_fee_defaulters_use_credit(self):
		pay(self.s["c"], "_Test T1", 300000)
		pay(self.s["c"], "_Test T3", 1000000)
		with as_user(ACCOUNTANT):
			data = rows("Fee Collection and Defaulters", only_defaulters=1, **{"class": "_Test FORM 1"})
		c = next(r for r in data if r["student"] == self.s["c"])
		# T1 owes 300,000 - 200,000 credit; T2 750,000; T3 is paid
		self.assertEqual((c["credit_applied"], c["outstanding"]), (200000, 100000 + 750000))

	def test_pending_comments(self):
		with as_user(TEACHER_2):  # class teacher of FORM 2 only
			self.assertEqual(
				rows("Pending Report Card Comments", term="_Test T2", comment="Class Teacher"), []
			)
			with enforce_roles():
				self.assertRaises(
					frappe.PermissionError,
					rows,
					"Pending Report Card Comments",
					term="_Test T2",
					comment="Headmaster",
				)
		with as_user(HEADMASTER):
			pending = rows("Pending Report Card Comments", term="_Test T2", comment="Headmaster")
		self.assertEqual(len(pending), 5)
