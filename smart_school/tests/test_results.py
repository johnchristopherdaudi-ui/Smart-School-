"""Result engine (#9, #10, #11, D2, D3): weighted subject scores, rounding, divisions, lifecycle and validation."""

import frappe

from smart_school.results import get_grade, get_subject_scores, round_half_up
from smart_school.tests.factory import SUBJECTS, SchoolTestCase, add_result, make_exam


class TestResultEngine(SchoolTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.mid = make_exam("_Test Mid", "_Test T3", "_Test FORM 1", max_marks=100, weight=40)
		cls.final = make_exam("_Test Final", "_Test T3", "_Test FORM 1", max_marks=50, weight=60)

	def term_result(self, student):
		return frappe.db.get_value(
			"Student Term Result",
			{"student": student, "term": "_Test T3"},
			["average", "subjects_count", "total_points", "division"],
			as_dict=True,
		)

	def test_round_half_up(self):
		self.assertEqual([round_half_up(v) for v in (74.5, 64.5, 44.49, 0.5)], [75, 65, 44, 1])

	def test_weighted_score_and_out_of_50(self):
		add_result(self.s["a"], self.mid, "_T MATH", 70)  # 70 %
		doc = add_result(self.s["a"], self.final, "_T MATH", 40)  # 40/50 = 80 %
		self.assertEqual((doc.percentage, doc.grade), (80, "A"))
		self.assertEqual(get_subject_scores(self.s["a"], "_Test T3")[0]["_T MATH"], 76)  # 0.4*70 + 0.6*80

	def test_74_5_is_an_a(self):
		add_result(self.s["b"], self.mid, "_T ENGLISH", 74.5)
		add_result(self.s["b"], self.final, "_T ENGLISH", 37.25)
		score = get_subject_scores(self.s["b"], "_Test T3")[0]["_T ENGLISH"]
		self.assertEqual((score, get_grade(score)[0]), (75, "A"))

	def test_plain_average_without_weights(self):
		exam_1 = make_exam("_Test Plain 1", "_Test T3", "_Test FORM 2")
		exam_2 = make_exam("_Test Plain 2", "_Test T3", "_Test FORM 2")
		add_result(self.s["e"], exam_1, "_T MATH", 70)
		add_result(self.s["e"], exam_2, "_T MATH", 80)
		self.assertEqual(get_subject_scores(self.s["e"], "_Test T3")[0]["_T MATH"], 75)

	def test_best_seven_division_and_incomplete(self):
		marks = [80, 76, 60, 50, 40, 30, 20]  # points 1+1+3+3+4+4+5 = 21 -> Division II
		for subject, mark in zip(SUBJECTS, marks):
			add_result(self.s["c"], self.mid, subject, mark)
		result = self.term_result(self.s["c"])
		self.assertEqual(
			(result.subjects_count, result.total_points, result.division), (7, 21, "Division II")
		)

		for subject in SUBJECTS[:6]:
			add_result(self.s["d"], self.mid, subject, 70)
		self.assertEqual(self.term_result(self.s["d"]).division, "Incomplete")

	def test_marks_outside_range_rejected(self):
		self.assertRaises(frappe.ValidationError, add_result, self.s["a"], self.final, "_T PHYSICS", 51)
		self.assertRaises(frappe.ValidationError, add_result, self.s["a"], self.final, "_T HISTORY", -1)

	def test_amend_after_cancel(self):
		original = add_result(self.s["b"], self.mid, "_T GEOGRAPHY", 20)
		original.cancel()
		self.assertFalse(
			frappe.db.exists(
				"Exam Result",
				{"student": self.s["b"], "exam": self.mid, "subject": "_T GEOGRAPHY", "docstatus": 1},
			)
		)
		amended = frappe.copy_doc(original)
		amended.amended_from = original.name
		amended.docstatus = 0  # as the desk's Amend button does
		amended.marks = 80
		amended.insert()
		amended.submit()
		self.assertEqual(amended.grade, "A")
		self.assertEqual(get_subject_scores(self.s["b"], "_Test T3")[0]["_T GEOGRAPHY"], 80)

	def test_duplicate_result_rejected(self):
		add_result(self.s["d"], self.final, "_T CIVICS", 30)
		self.assertRaises(frappe.ValidationError, add_result, self.s["d"], self.final, "_T CIVICS", 31)


class TestGradingAndExamRules(SchoolTestCase):
	def test_overlapping_ranges_rejected(self):
		grade = frappe.get_doc(
			{"doctype": "Grading System", "grade": "A", "minimum_mark": 70, "maximum_mark": 80, "points": 9}
		)
		self.assertRaises(frappe.ValidationError, grade.insert, set_name="_Test Grade")
		division = frappe.get_doc(
			{"doctype": "Division Grading", "division": "_Test", "minimum_points": 30, "maximum_points": 40}
		)
		self.assertRaises(frappe.ValidationError, division.insert, set_name="_Test Division")

	def test_weights_all_or_none_and_at_most_100(self):
		make_exam("_Test W1", "_Test T2", "_Test FORM 2", weight=40)
		unweighted = frappe.get_doc(
			{"doctype": "Exam", "exam_name": "_Test W2", "term": "_Test T2", "class": "_Test FORM 2"}
		)
		self.assertRaises(frappe.ValidationError, unweighted.insert)
		too_much = frappe.get_doc(
			{
				"doctype": "Exam",
				"exam_name": "_Test W3",
				"term": "_Test T2",
				"class": "_Test FORM 2",
				"weight": 70,
			}
		)
		self.assertRaises(frappe.ValidationError, too_much.insert)

	def test_term_dates_validated(self):
		term = frappe.get_doc(
			{
				"doctype": "Term",
				"term_name": "Term 1",
				"academic_year": "_Test AY",
				"start_date": frappe.utils.add_days(frappe.utils.today(), 10),
				"end_date": frappe.utils.add_days(frappe.utils.today(), 20),
			}
		)
		self.assertRaises(frappe.ValidationError, term.insert, set_name="_Test Overlap")  # overlaps _Test T3
