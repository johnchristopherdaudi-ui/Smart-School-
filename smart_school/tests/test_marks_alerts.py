"""Marks alerts: the statistical and integrity checks, saving and resolving alerts, the warning before
publishing, and who may see the alerts."""

import json
from unittest.mock import patch

import frappe
from frappe.desk.form import assign_to
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from smart_school import marks_alerts as ma
from smart_school.tests.factory import (
	HEADMASTER,
	PARENT_1,
	TEACHER_1,
	SchoolTestCase,
	add_result,
	as_user,
	call,
	enforce_roles,
	make_exam,
	make_student,
)

SETTINGS = frappe._dict(
	enabled=1,
	min_class_size=10,
	identical_share=40,
	zero_share=20,
	round_share=80,
	min_std=3,
	history_min_exams=4,
	class_z=3.5,
	class_min_diff=10,
	student_z=3.5,
	student_min_jump=20,
	zero_drop_from=30,
)
NATURAL = [23, 37, 41, 48, 52, 56, 61, 64, 68, 73, 79, 88]
SIX_ALIKE = [50] * 6 + [23, 37, 41, 62, 68, 79]
CHECK_EXAM = "smart_school.marks_alerts.check_exam"
PUBLISH = "smart_school.results.publish_exam_results"


def types(findings):
	return sorted(f[0] for f in findings)


class TestStatistics(FrappeTestCase):
	def test_robust_z(self):
		# median 3, MAD 1
		self.assertAlmostEqual(ma.robust_z(10, [1, 2, 3, 4, 5]), 0.6745 * 7, places=4)
		self.assertIsNone(ma.robust_z(9, [4, 4, 4, 5]))  # MAD 0: no score rather than a division by 0

	def test_small_class_and_natural_marks_raise_nothing(self):
		self.assertEqual(ma.check_class_marks([50] * 9, 100, SETTINGS), [])
		self.assertEqual(ma.check_class_marks(NATURAL, 100, SETTINGS), [])

	def test_identical_marks_leave_out_zero_and_full_marks(self):
		self.assertEqual(types(ma.check_class_marks(SIX_ALIKE, 100, SETTINGS)), [ma.IDENTICAL])
		evidence = ma.check_class_marks(SIX_ALIKE, 100, SETTINGS)[0][2]
		self.assertEqual((evidence["mark"], evidence["count"], evidence["share"]), (50, 6, 50))

		full_marks = [100] * 6 + [23, 37, 41, 62, 68, 79]
		self.assertNotIn(ma.IDENTICAL, types(ma.check_class_marks(full_marks, 100, SETTINGS)))
		out_of_40 = [40] * 6 + [9, 13, 17, 22, 27, 31]
		self.assertNotIn(ma.IDENTICAL, types(ma.check_class_marks(out_of_40, 40, SETTINGS)))

	def test_zero_marks_have_their_own_check(self):
		six_zeros = [0] * 6 + [23, 37, 41, 62, 68, 79]
		self.assertEqual(types(ma.check_class_marks(six_zeros, 100, SETTINGS)), [ma.ZEROS])
		two_zeros = [0, 0] + NATURAL[:10]  # 16.7%, under 20%
		self.assertNotIn(ma.ZEROS, types(ma.check_class_marks(two_zeros, 100, SETTINGS)))

	def test_round_numbers_use_raw_marks(self):
		out_of_40 = [5, 10, 15, 20, 25, 30, 35, 5, 10, 15, 20, 25]
		self.assertEqual(types(ma.check_class_marks(out_of_40, 40, SETTINGS)), [ma.ROUND])
		# Even marks out of 40 are all multiples of 5 as percentages (30%, 35%, ...), but not as marks
		even_out_of_40 = [12, 14, 16, 18, 22, 24, 26, 28, 32, 34, 36, 38]
		self.assertEqual(ma.check_class_marks(even_out_of_40, 40, SETTINGS), [])

	def test_low_spread(self):
		close = [58, 59, 60, 61, 62, 63] * 2
		self.assertEqual(types(ma.check_class_marks(close, 100, SETTINGS)), [ma.LOW_SPREAD])
		self.assertEqual(ma.check_class_marks(close, 100, frappe._dict(SETTINGS, min_std=0)), [])

	def test_class_average_against_history(self):
		history = [50, 52, 48, 51, 49, 50]  # median 50, MAD 1
		finding = ma.check_class_average(70, history, SETTINGS)
		self.assertEqual(types(finding), [ma.CLASS_AVERAGE])
		self.assertEqual(finding[0][2]["robust_z"], round(0.6745 * 20, 2))
		self.assertEqual(ma.check_class_average(51, history, SETTINGS), [])
		self.assertEqual(ma.check_class_average(70, history[:3], SETTINGS), [])  # too little history
		self.assertEqual(ma.check_class_average(70, [50] * 6, SETTINGS), [])  # MAD 0
		self.assertEqual(ma.check_class_average(None, history, SETTINGS), [])

	def test_class_average_needs_a_real_difference(self):
		# Averages of a few exams can sit very close together: z is huge, but 3 points is not unusual
		history = [50, 50.2, 49.8, 50.1, 49.9]
		self.assertGreater(ma.robust_z(53, history), 3.5)
		self.assertEqual(ma.check_class_average(53, history, SETTINGS), [])
		self.assertEqual(types(ma.check_class_average(61, history, SETTINGS)), [ma.CLASS_AVERAGE])

	def test_student_change_is_measured_against_the_class(self):
		variation = [-3, -2, -1, 0, 1, 2, 3, -2, 1, 0, 2]
		pairs = {f"S{i}": (50, 50 + v, "E0") for i, v in enumerate(variation)}
		pairs["JUMP"] = (40, 75, "E0")
		findings = ma.check_student_changes(pairs, SETTINGS)
		self.assertEqual([f[2]["student"] for f in findings], ["JUMP"])
		self.assertEqual(findings[0][2]["previous_exam"], "E0")

		# A hard exam that lowers everyone raises nothing
		hard = {f"S{i}": (60, 40 + v, "E0") for i, v in enumerate(variation + [1])}
		self.assertEqual(ma.check_student_changes(hard, SETTINGS), [])

	def test_dropped_to_zero_is_always_medium(self):
		variation = [-3, -2, -1, 0, 1, 2, 3, -2, 1, 0]
		pairs = {f"S{i}": (50, 50 + v, "E0") for i, v in enumerate(variation)}
		pairs["ZERO"] = (59, 0, "E0")  # z about -3.9: below the statistical threshold on its own
		pairs["WEAK"] = (20, 0, "E0")  # had less than 30%: not this rule
		strict = frappe._dict(SETTINGS, student_z=100)
		findings = ma.check_student_changes(pairs, strict)
		self.assertEqual([(f[0], f[1], f[2]["student"]) for f in findings], [(ma.ZERO_DROP, "Medium", "ZERO")])

		# One alert per student: not also an Unusual Student Change
		findings = ma.check_student_changes(pairs, SETTINGS)
		self.assertEqual([f[0] for f in findings if f[2]["student"] == "ZERO"], [ma.ZERO_DROP])
		# Always, even in a class too small for statistics
		small = {k: pairs[k] for k in ("S0", "S1", "ZERO")}
		self.assertEqual(types(ma.check_student_changes(small, SETTINGS)), [ma.ZERO_DROP])
		# Not when the whole class has many zeros: that alert covers them
		self.assertEqual(
			[f for f in ma.check_student_changes(pairs, strict, class_has_many_zeros=True)], []
		)

	def test_student_change_needs_a_minimum_jump(self):
		changes = [-1, 1] * 5 + [0, 10]  # z of the last one is about 6.4, but it moved only 9.5 points more
		pairs = {f"S{i}": (50, 50 + c, "E0") for i, c in enumerate(changes)}
		self.assertEqual(ma.check_student_changes(pairs, SETTINGS), [])
		loose = frappe._dict(SETTINGS, student_min_jump=5)
		self.assertEqual([f[2]["student"] for f in ma.check_student_changes(pairs, loose)], ["S11"])


class TestMarksAlerts(SchoolTestCase):
	"""Data is rolled back per suite, not per test: each statistical test uses its own subject so one
	test's marks never become another test's history."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.set_single_value("Smart School Settings", dict(ma.DEFAULTS))
		cls.students = [
			make_student(f"_Test MA Student {i:02d}", "_Test FORM 1", "Female" if i % 2 else "Male")
			for i in range(12)
		]

	def enter(self, exam, subject, marks):
		return [add_result(student, exam, subject, m) for student, m in zip(self.students, marks)]

	def alerts(self, exam, **filters):
		return frappe.get_all(
			"Marks Alert",
			filters={"exam": exam, **filters},
			fields=[
				"name",
				"alert_type",
				"status",
				"severity",
				"student",
				"subject",
				"related_user",
				"evidence",
			],
			order_by="creation asc",
		)

	def amend(self, result, marks):
		result.flags.ignore_permissions = True
		result.cancel()
		new = frappe.copy_doc(result)
		new.docstatus = 0
		new.amended_from = result.name
		new.marks = marks
		new.insert(ignore_permissions=True)
		new.submit()
		return new

	def review(self, alert, status="Reviewed-OK"):
		with as_user(HEADMASTER):
			doc = frappe.get_doc("Marks Alert", alert)
			doc.status = status
			doc.save()
		return doc

	# ---------- statistical alerts ----------

	def test_alert_saved_once_and_a_reviewed_alert_stays_reviewed(self):
		exam = make_exam("_Test MA Same", "_Test T3", "_Test FORM 1")
		self.enter(exam, "_T MATH", SIX_ALIKE)
		ma.run_exam_checks(exam)
		ma.run_exam_checks(exam)
		alerts = self.alerts(exam)
		self.assertEqual(
			[(a.alert_type, a.status, a.severity) for a in alerts], [(ma.IDENTICAL, "Open", "Medium")]
		)
		self.assertEqual(json.loads(alerts[0].evidence)["count"], 6)
		message = frappe.db.get_value("Marks Alert", alerts[0].name, "message")
		self.assertIn("6 of 12 students have exactly 50", message)

		doc = self.review(alerts[0].name)
		self.assertEqual(doc.reviewer, HEADMASTER)
		self.assertTrue(doc.reviewed_on)
		ma.run_exam_checks(exam)
		self.assertEqual([a.status for a in self.alerts(exam)], ["Reviewed-OK"])

	def test_auto_resolved_when_the_pattern_is_gone_and_reopened_when_it_returns(self):
		exam = make_exam("_Test MA Fix", "_Test T3", "_Test FORM 1")
		results = self.enter(exam, "_T ENGLISH", SIX_ALIKE)
		ma.run_exam_checks(exam)
		alert = self.alerts(exam)[0].name

		fixed = [self.amend(results[0], 57), self.amend(results[1], 44)]  # 4 of 12 now have 50
		ma.run_exam_checks(exam)
		doc = frappe.get_doc("Marks Alert", alert)
		self.assertEqual(doc.status, "Auto-resolved")
		self.assertFalse(doc.reviewer)
		self.assertTrue(doc.review_note)

		self.amend(fixed[0], 50)  # 5 of 12: 41.7%
		ma.run_exam_checks(exam)
		doc.reload()
		self.assertEqual((doc.status, doc.reviewed_on, doc.review_note), ("Open", None, None))
		self.assertEqual(len(self.alerts(exam)), 1)

	def test_only_the_checks_auto_resolve_and_never_integrity_alerts(self):
		exam = make_exam("_Test MA Rules", "_Test T3", "_Test FORM 1")
		statistical = ma.save_alert(
			"test|statistical", ma.IDENTICAL, "Medium", frappe.get_doc("Exam", exam), {}, "test"
		)
		with as_user(HEADMASTER):
			statistical = frappe.get_doc("Marks Alert", statistical.name)
			statistical.status = "Auto-resolved"
			self.assertRaises(frappe.ValidationError, statistical.save)

		integrity = ma.save_alert(
			"test|integrity", ma.CHANGED_AFTER_PUBLISH, "High", frappe.get_doc("Exam", exam), {}, "test"
		)
		integrity = frappe.get_doc("Marks Alert", integrity.name)
		integrity.status = "Auto-resolved"
		integrity.flags.from_checks = True
		self.assertRaises(frappe.ValidationError, integrity.save, ignore_permissions=True)

	def test_class_average_and_student_change_against_earlier_exams(self):
		base = [35, 40, 45, 48, 50, 52, 55, 58, 60, 62, 44, 51]
		for name, term, shift in (
			("_Test MA H1", "_Test T1", 0),
			("_Test MA H2", "_Test T1", 2),
			("_Test MA H3", "_Test T2", -2),
			("_Test MA H4", "_Test T2", 1),
		):
			earlier = make_exam(name, term, "_Test FORM 1")
			self.enter(earlier, "_T BIOLOGY", [m + shift for m in base])

		exam = make_exam("_Test MA Now", "_Test T3", "_Test FORM 1")
		variation = [30, 1, -1, 2, -2, 0, 1, -1, 0, 2, -2, 0]  # the first student moves 30 points more
		self.enter(exam, "_T BIOLOGY", [m + 25 + v for m, v in zip(base, variation)])
		ma.run_exam_checks(exam)

		average = self.alerts(exam, alert_type=ma.CLASS_AVERAGE)
		self.assertEqual(len(average), 1)
		self.assertEqual(json.loads(average[0].evidence)["history_exams"], 4)

		changes = self.alerts(exam, alert_type=ma.STUDENT_CHANGE)
		self.assertEqual([(a.student, a.severity) for a in changes], [(self.students[0], "Medium")])
		evidence = json.loads(changes[0].evidence)
		self.assertEqual(
			frappe.db.get_value("Exam", evidence["previous_exam"], "exam_name"), "_Test MA H4"
		)
		self.assertEqual(evidence["class_median_change"], 24)

	def test_many_zeros_in_a_class_raise_one_alert_not_one_per_student(self):
		earlier = make_exam("_Test MA Zero Before", "_Test T2", "_Test FORM 1")
		self.enter(earlier, "_T HISTORY", NATURAL)
		exam = make_exam("_Test MA Zero After", "_Test T3", "_Test FORM 1")
		self.enter(exam, "_T HISTORY", [0, 0, 0, *NATURAL[3:]])  # three students who had 23-41% now have 0
		ma.run_exam_checks(exam)
		self.assertEqual([a.alert_type for a in self.alerts(exam, subject="_T HISTORY")], [ma.ZEROS])

		self.amend(frappe.get_doc("Exam Result", {"exam": exam, "student": self.students[0], "docstatus": 1}), 30)
		self.amend(frappe.get_doc("Exam Result", {"exam": exam, "student": self.students[1], "docstatus": 1}), 35)
		ma.run_exam_checks(exam)  # one zero left: 8%, so no class alert, and the student gets their own
		open_alerts = self.alerts(exam, subject="_T HISTORY", status="Open")
		self.assertEqual([(a.alert_type, a.student) for a in open_alerts], [(ma.ZERO_DROP, self.students[2])])

	def test_thresholds_come_from_settings(self):
		exam = make_exam("_Test MA Settings", "_Test T3", "_Test FORM 1")
		self.enter(exam, "_T KISWAHILI", SIX_ALIKE)
		frappe.db.set_single_value("Smart School Settings", "alert_identical_share", 60)
		ma.run_exam_checks(exam)
		self.assertEqual(self.alerts(exam), [])

		frappe.db.set_single_value("Smart School Settings", "alert_identical_share", 40)
		frappe.db.set_single_value("Smart School Settings", "enable_marks_alerts", 0)
		ma.run_nightly_checks()
		with as_user(HEADMASTER), enforce_roles():
			self.assertEqual(call(CHECK_EXAM, exam=exam), [])
		self.assertEqual(self.alerts(exam), [])

		frappe.db.set_single_value("Smart School Settings", "enable_marks_alerts", 1)
		ma.run_nightly_checks()
		self.assertEqual([a.alert_type for a in self.alerts(exam)], [ma.IDENTICAL])

	def test_settings_validation(self):
		settings = frappe.get_single("Smart School Settings")
		settings.alert_min_class_size = 2
		self.assertRaises(frappe.ValidationError, settings.save)
		settings.reload()
		settings.alert_zero_share = 0
		self.assertRaises(frappe.ValidationError, settings.save)

	# ---------- integrity alerts ----------

	def publish_now(self, exam):
		now = now_datetime()
		frappe.db.set_value(
			"Exam", exam, {"results_published": 1, "published_on": now, "first_published_on": now}
		)

	def test_changed_after_publish_applies_to_headmaster_too(self):
		exam = make_exam("_Test MA Pub", "_Test T3", "_Test FORM 1")
		results = self.enter(exam, "_T MATH", [60, 45, 70])
		self.publish_now(exam)

		with as_user(HEADMASTER):
			amended = self.amend(results[0], 72)
		alerts = self.alerts(exam, alert_type=ma.CHANGED_AFTER_PUBLISH)
		self.assertEqual(len(alerts), 1)  # the cancel and the amendment are one change
		alert = frappe.get_doc("Marks Alert", alerts[0].name)
		self.assertEqual(
			(alert.severity, alert.related_user, alert.student), ("High", HEADMASTER, self.students[0])
		)
		self.assertIn("was changed from 60 to 72 after the results were published", alert.message)
		changes = json.loads(alert.evidence)["changes"]
		self.assertEqual([c["action"] for c in changes], ["cancelled", "submitted"])

		# The nightly run finds the same changes and adds nothing; the statistics never close it
		ma.find_changes_after_publish()
		ma.run_exam_checks(exam)
		alert.reload()
		self.assertEqual((alert.status, len(json.loads(alert.evidence)["changes"])), ("Open", 2))

		# After review, a new change opens a new alert instead of reopening the reviewed one
		self.review(alert.name)
		with as_user(TEACHER_1):
			self.amend(amended, 75)
		alerts = self.alerts(exam, alert_type=ma.CHANGED_AFTER_PUBLISH)
		self.assertEqual([a.status for a in alerts], ["Reviewed-OK", "Open"])
		self.assertEqual(alerts[1].related_user, TEACHER_1)

	def test_nightly_run_finds_direct_database_edits(self):
		exam = make_exam("_Test MA Direct", "_Test T3", "_Test FORM 1")
		results = self.enter(exam, "_T ENGLISH", [60, 45])
		self.publish_now(exam)
		frappe.db.set_value("Exam Result", results[1].name, "marks", 99)
		ma.find_changes_after_publish()

		alerts = self.alerts(exam, alert_type=ma.CHANGED_AFTER_PUBLISH)
		self.assertEqual([a.student for a in alerts], [self.students[1]])
		self.assertEqual(json.loads(alerts[0].evidence)["changes"][0]["action"], "updated")

	def test_unassigned_entries_but_not_by_headmaster(self):
		exam = make_exam("_Test MA Entry", "_Test T3", "_Test FORM 1")

		def enter_as(user, subject):
			with as_user(user):
				for student in self.students[:2]:
					doc = frappe.get_doc(
						{
							"doctype": "Exam Result",
							"student": student,
							"exam": exam,
							"subject": subject,
							"marks": 50,
						}
					)
					doc.insert(ignore_permissions=True)
					doc.submit()

		enter_as(TEACHER_1, "_T PHYSICS")  # Teacher One teaches only MATH and ENGLISH in FORM 1
		enter_as(TEACHER_1, "_T MATH")
		enter_as(HEADMASTER, "_T HISTORY")
		enter_as("Administrator", "_T GEOGRAPHY")
		ma.run_exam_checks(exam)

		alerts = self.alerts(exam)
		self.assertEqual(
			[(a.alert_type, a.subject, a.related_user) for a in alerts],
			[(ma.UNASSIGNED, "_T PHYSICS", TEACHER_1)],
		)
		self.assertEqual(json.loads(alerts[0].evidence)["results"], 2)

	def test_unpublish_change_and_publish_again_is_still_seen(self):
		exam = make_exam("_Test MA Unpub", "_Test T3", "_Test FORM 1")
		results = self.enter(exam, "_T HISTORY", [60, 45, 70])
		with as_user(HEADMASTER), enforce_roles(), patch("frappe.enqueue"):
			call(PUBLISH, exam=exam)
			first = frappe.db.get_value("Exam", exam, "first_published_on")
			call("smart_school.results.unpublish_exam_results", exam=exam)

		unpublished = self.alerts(exam, alert_type=ma.UNPUBLISHED)
		self.assertEqual(
			[(a.severity, a.status, a.related_user) for a in unpublished], [("Medium", "Open", HEADMASTER)]
		)
		comments = frappe.get_all(
			"Comment", filters={"reference_doctype": "Exam", "reference_name": exam}, pluck="content"
		)
		self.assertTrue(any(c.startswith("Results unpublished by ") for c in comments), comments)

		# Marks changed while unpublished: the form hook and the nightly run both see it
		self.amend(results[0], 80)
		frappe.db.set_value("Exam Result", results[1].name, "marks", 90)
		ma.find_changes_after_publish()
		changed = self.alerts(exam, alert_type=ma.CHANGED_AFTER_PUBLISH)
		self.assertEqual(sorted(a.student for a in changed), sorted(self.students[:2]))

		with as_user(HEADMASTER), enforce_roles(), patch("frappe.enqueue"):
			call(PUBLISH, exam=exam)
		published_on, first_published_on = frappe.db.get_value(
			"Exam", exam, ["published_on", "first_published_on"]
		)
		self.assertEqual(first_published_on, first)
		self.assertGreater(published_on, first)

		# The statistics never close integrity alerts, and unpublishing twice is not possible
		ma.run_exam_checks(exam)
		self.assertEqual({a.status for a in self.alerts(exam)}, {"Open"})
		frappe.db.set_value("Exam", exam, "results_published", 0)
		with as_user(HEADMASTER), enforce_roles():
			self.assertRaises(
				frappe.ValidationError, call, "smart_school.results.unpublish_exam_results", exam=exam
			)

	def test_integrity_checks_run_when_statistics_are_off(self):
		exam = make_exam("_Test MA Off", "_Test T3", "_Test FORM 1")
		results = self.enter(exam, "_T ENGLISH", SIX_ALIKE)
		ma.run_exam_checks(exam)
		self.assertEqual([a.alert_type for a in self.alerts(exam)], [ma.IDENTICAL])

		frappe.db.set_single_value("Smart School Settings", "enable_marks_alerts", 0)
		with as_user(TEACHER_1):
			doc = frappe.get_doc(
				{"doctype": "Exam Result", "student": self.students[0], "exam": exam, "subject": "_T PHYSICS"}
			)
			doc.marks = 50
			doc.insert(ignore_permissions=True)
			doc.submit()
		self.amend(results[0], 50)  # the identical-marks pattern goes away...
		ma.run_nightly_checks()
		self.publish_now(exam)
		self.amend(results[6], 30)
		with as_user(HEADMASTER), enforce_roles(), patch("frappe.enqueue"):
			warning = call(CHECK_EXAM, exam=exam)
			call("smart_school.results.unpublish_exam_results", exam=exam)
		frappe.db.set_single_value("Smart School Settings", "enable_marks_alerts", 1)

		# ...but with the statistics off, their alert is left as it was
		alerts = {a.alert_type: a.status for a in self.alerts(exam)}
		self.assertEqual(
			alerts,
			{
				ma.IDENTICAL: "Open",
				ma.UNASSIGNED: "Open",
				ma.CHANGED_AFTER_PUBLISH: "Open",
				ma.UNPUBLISHED: "Open",
			},
		)
		self.assertEqual(
			sorted(a.alert_type for a in warning), sorted([ma.IDENTICAL, ma.UNASSIGNED, ma.CHANGED_AFTER_PUBLISH])
		)

	# ---------- before publishing ----------

	def test_publish_warns_but_never_blocks(self):
		exam = make_exam("_Test MA Warn", "_Test T3", "_Test FORM 1")
		self.enter(exam, "_T CIVICS", SIX_ALIKE)
		with as_user(HEADMASTER), enforce_roles(), patch("frappe.enqueue"):
			warning = call(CHECK_EXAM, exam=exam)
			self.assertEqual([a.alert_type for a in warning], [ma.IDENTICAL])
			call(PUBLISH, exam=exam)

		self.assertEqual(frappe.db.get_value("Exam", exam, "results_published"), 1)
		comments = frappe.get_all(
			"Comment", filters={"reference_doctype": "Exam", "reference_name": exam}, pluck="content"
		)
		self.assertTrue(
			any(c.startswith("Published with 1 open marks alert by ") for c in comments), comments
		)

	def test_publish_without_alerts_or_with_a_failing_check(self):
		clean = make_exam("_Test MA Clean", "_Test T3", "_Test FORM 1")
		self.enter(clean, "_T GEOGRAPHY", NATURAL)
		broken = make_exam("_Test MA Broken", "_Test T3", "_Test FORM 1")
		with as_user(HEADMASTER), enforce_roles(), patch("frappe.enqueue"):
			call(PUBLISH, exam=clean)
			with patch("smart_school.marks_alerts.run_exam_checks", side_effect=Exception("check failed")):
				call(PUBLISH, exam=broken)

		for exam in (clean, broken):
			self.assertEqual(frappe.db.get_value("Exam", exam, "results_published"), 1)
			self.assertFalse(
				frappe.get_all("Comment", filters={"reference_doctype": "Exam", "reference_name": exam})
			)

	# ---------- who sees alerts ----------

	def test_only_headmaster_sees_alerts_and_a_teacher_sees_the_assigned_one(self):
		exam = frappe.get_doc("Exam", make_exam("_Test MA Perm", "_Test T3", "_Test FORM 1"))
		assigned = ma.save_alert("test|assigned", ma.IDENTICAL, "Medium", exam, {}, "test").name
		other = ma.save_alert("test|other", ma.ZEROS, "Medium", exam, {}, "test").name

		def visible(user):
			with as_user(user):
				try:
					return sorted(frappe.get_list("Marks Alert", filters={"exam": exam.name}, pluck="name"))
				except frappe.PermissionError:
					return []

		self.assertEqual(visible(HEADMASTER), sorted([assigned, other]))
		self.assertEqual(visible(TEACHER_1), [])
		self.assertEqual(visible(PARENT_1), [])
		with as_user(TEACHER_1), enforce_roles():
			self.assertRaises(frappe.PermissionError, call, CHECK_EXAM, exam=exam.name)

		with as_user(HEADMASTER):
			assign_to.add({"assign_to": [TEACHER_1], "doctype": "Marks Alert", "name": assigned})

		self.assertEqual(visible(TEACHER_1), [assigned])
		self.assertTrue(frappe.has_permission("Marks Alert", "read", doc=assigned, user=TEACHER_1))
		self.assertFalse(frappe.has_permission("Marks Alert", "write", doc=assigned, user=TEACHER_1))
		self.assertFalse(frappe.has_permission("Marks Alert", "read", doc=other, user=TEACHER_1))
		self.assertFalse(frappe.has_permission("Marks Alert", "read", doc=assigned, user=PARENT_1))
