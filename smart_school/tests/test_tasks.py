"""#20-#22: risk score, performance insights, academic records and the promotion tool."""

import json

import frappe
from frappe.utils import add_days, today

from smart_school import tasks
from smart_school.tests.factory import (
	SUBJECTS,
	TEACHER_1,
	SchoolTestCase,
	add_result,
	as_user,
	enforce_roles,
	make_exam,
	no_commit,
)


class TestRiskScore(SchoolTestCase):
	def test_parts_weights_and_level(self):
		student = self.s["c"]
		previous = make_exam("_Test Risk Prev", "_Test T2", "_Test FORM 1")
		current = make_exam("_Test Risk Now", "_Test T3", "_Test FORM 1")
		for subject in SUBJECTS[:7]:
			add_result(student, previous, subject, 60)
			add_result(
				student, current, subject, {"_T MATH": 20, "_T ENGLISH": 25}.get(subject, 40)
			)  # avg 35, two F
		start = frappe.db.get_value("Term", "_Test T3", "start_date")
		for i, status in enumerate(["Absent", "Absent", "Late", "Late", "Excused"] + ["Present"] * 5):
			frappe.get_doc(
				{"doctype": "Attendance", "student": student, "date": add_days(start, i), "status": status}
			).insert(ignore_permissions=True)
		for severity in ("Minor", "Serious"):
			frappe.get_doc(
				{
					"doctype": "Discipline Record",
					"student": student,
					"date": today(),
					"incident_type": "Lateness",
					"severity": severity,
				}
			).insert(ignore_permissions=True)

		modified = frappe.db.get_value("Student", student, "modified")
		score, level = tasks.calculate_risk_score(student)
		breakdown = json.loads(frappe.db.get_value("Student", student, "risk_breakdown"))

		# attendance (2 + 0.5*2)/10 = 30% -> 1.0*25; discipline 5/8*20; low average (45-35)/45*25; F 2/3*15; drop 25 -> 15
		self.assertEqual(
			{k: v["score"] for k, v in breakdown.items() if isinstance(v, dict)},
			{
				"attendance": 25.0,
				"discipline": 12.5,
				"low_average": 5.6,
				"failed_subjects": 10.0,
				"decline": 15.0,
			},
		)
		self.assertEqual((score, level), (68.1, "High"))
		self.assertEqual(breakdown["attendance"]["excused"], 1)
		self.assertEqual(frappe.db.get_value("Student", student, "modified"), modified)

	def test_levels_and_settings_validation(self):
		settings = frappe.get_cached_doc("Smart School Settings")
		self.assertEqual(
			[tasks.get_risk_level(x, settings) for x in (29.9, 30, 59.9, 60)],
			["Low", "Medium", "Medium", "High"],
		)
		doc = frappe.get_doc("Smart School Settings")
		doc.risk_weight_decline = 5
		self.assertRaises(frappe.ValidationError, doc.save)


class TestInsightsRecordsAndPromotion(SchoolTestCase):
	def test_insights_created_then_updated(self):
		t1 = make_exam("_Test Ins T1", "_Test T1", "_Test FORM 1")
		t2 = make_exam("_Test Ins T2", "_Test T2", "_Test FORM 1")
		for subject in SUBJECTS[:7]:
			add_result(self.s["a"], t1, subject, 60)
			add_result(self.s["a"], t2, subject, 40)
		tasks.check_class_performance("_Test FORM 1")
		insight = frappe.db.get_value(
			"Performance Insight",
			{"class": "_Test FORM 1", "term": "_Test T2", "subject": ["is", "not set"]},
			["name", "change_percentage"],
			as_dict=True,
		)
		self.assertEqual(insight.change_percentage, -33.3)
		self.assertTrue(
			frappe.db.exists(
				"Performance Insight", {"class": "_Test FORM 1", "term": "_Test T2", "subject": "_T MATH"}
			)
		)

		for subject in SUBJECTS[:7]:
			add_result(self.s["b"], t1, subject, 60)
			add_result(self.s["b"], t2, subject, 60)
		tasks.check_class_performance("_Test FORM 1")
		updated = frappe.db.get_value(
			"Performance Insight",
			{"class": "_Test FORM 1", "term": "_Test T2", "subject": ["is", "not set"]},
			["name", "change_percentage"],
			as_dict=True,
		)
		self.assertEqual(updated.name, insight.name)
		self.assertEqual(updated.change_percentage, -16.7)

	def test_promotion_tool(self):
		frappe.set_user("Administrator")
		with as_user(TEACHER_1), enforce_roles():
			tool = frappe.get_doc("Student Promotion Tool")
			tool.from_class, tool.academic_year = "_Test FORM 1", "_Test AY"
			self.assertRaises(frappe.PermissionError, tool.get_students)

		tool = frappe.get_doc("Student Promotion Tool")
		tool.from_class, tool.academic_year = "_Test FORM 1", "_Test AY"
		tool.get_students()
		for row in tool.students:
			if row.student == self.s["b"]:
				row.action = "Repeat"
		rows = [r.as_dict() for r in tool.students]
		counts = tool.promote()
		self.assertEqual(frappe.db.get_value("Student", self.s["a"], "current_class"), "_Test FORM 2")
		self.assertEqual(frappe.db.get_value("Student", self.s["b"], "current_class"), "_Test FORM 1")
		self.assertEqual(
			frappe.db.get_value(
				"Student Academic Record", {"student": self.s["a"], "academic_year": "_Test AY"}, "class"
			),
			"_Test FORM 1",
		)
		self.assertEqual(counts["repeating"], 1)

		again = frappe.get_doc("Student Promotion Tool")
		again.from_class, again.academic_year = "_Test FORM 1", "_Test AY"
		for r in rows:
			again.append("students", {"student": r.student, "action": r.action})
		records = frappe.db.count("Student Academic Record", {"academic_year": "_Test AY"})
		self.assertEqual(again.promote()["skipped"], counts["promoted"])
		self.assertEqual(frappe.db.count("Student Academic Record", {"academic_year": "_Test AY"}), records)

	def test_top_class_graduates(self):
		student = (
			frappe.get_doc(
				{
					"doctype": "Student",
					"full_name": "_Test Leaver",
					"current_class": "_Test FORM 4",
					"status": "Active",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		tool = frappe.get_doc("Student Promotion Tool")
		tool.from_class, tool.academic_year = "_Test FORM 4", "_Test AY"
		tool.get_students()
		self.assertEqual(tool.to_class, "Graduated")
		tool.promote()
		self.assertEqual(frappe.db.get_value("Student", student, "status"), "Graduated")

	def test_academic_records_for_ended_years(self):
		frappe.get_doc(
			{
				"doctype": "Academic Year",
				"year": "_Test Old AY",
				"start_date": add_days(today(), -700),
				"end_date": add_days(today(), -400),
			}
		).insert(ignore_permissions=True, set_name="_Test Old AY")
		frappe.get_doc(
			{
				"doctype": "Term",
				"term_name": "Term 3",
				"academic_year": "_Test Old AY",
				"start_date": add_days(today(), -500),
				"end_date": add_days(today(), -401),
			}
		).insert(ignore_permissions=True, set_name="_Test Old T3")
		frappe.get_doc(
			{
				"doctype": "Student Term Result",
				"student": self.s["e"],
				"term": "_Test Old T3",
				"class": "_Test FORM 1",
				"average": 51,
				"division": "Division III",
			}
		).insert(ignore_permissions=True)
		with no_commit():  # the daily job commits
			tasks.create_academic_records_for_ended_years()
		self.assertEqual(
			frappe.db.get_value(
				"Student Academic Record", {"student": self.s["e"], "academic_year": "_Test Old AY"}, "class"
			),
			"_Test FORM 1",
		)
