"""Early-warning model: features and labels, the time split, the decision against the rule-based score, the
model file, predictions with reasons, the data guard and who may train or read."""

import json
from datetime import date
from unittest.mock import patch

import frappe

from smart_school import demo_data, risk_model
from smart_school.results import get_subject_scores
from smart_school.tasks import SEVERITY_POINTS
from smart_school.tests.factory import (
	HEADMASTER,
	PARENT_1,
	TEACHER_1,
	SchoolTestCase,
	as_user,
	call,
	enforce_roles,
)

AS_OF = date(2025, 12, 20)  # 2023-2025, every term finished


def metrics(ci_low, model_precision, rule_precision=0.5):
	return {
		"bootstrap": {"ci_low": ci_low, "ci_high": ci_low + 0.1},
		"model": {"auc": 0.8, "precision_top": model_precision},
		"rule": {"auc": 0.75, "precision_top": rule_precision},
	}


class TestRiskModel(SchoolTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.flags.mute_emails = True
		plan = demo_data.build_plan(seed=5, as_of=AS_OF, students_per_form=12)
		demo_data.write_plan(plan, fees=False)
		cls.data = risk_model.SchoolData()
		cls.rows = risk_model.build_rows(cls.data)
		cls.model = risk_model.train_model()

	def test_features_follow_the_definitions(self):
		self.assertNotIn("gender", risk_model.FEATURES)
		row = next(r for r in self.rows if not r.features["no_previous_term"] and r.features["absence_rate"])
		student, term = row.student, row.term

		statuses = frappe.get_all("Attendance", filters={"student": student, "term": term.name}, pluck="status")
		absence = (statuses.count("Absent") + 0.5 * statuses.count("Late")) / len(statuses)
		severities = frappe.get_all(
			"Discipline Record",
			filters={"student": student, "date": ["between", [term.start_date, term.end_date]]},
			pluck="severity",
		)
		previous = self.data.previous(term)
		average = frappe.db.get_value("Student Term Result", {"student": student, "term": term.name}, "average")
		before = frappe.db.get_value("Student Term Result", {"student": student, "term": previous.name}, "average")
		scores = get_subject_scores(student, term.name)[0]

		self.assertEqual(list(row.features), list(risk_model.FEATURES))
		self.assertAlmostEqual(row.features["absence_rate"], absence)
		self.assertEqual(row.features["discipline_points"], sum(SEVERITY_POINTS[s] for s in severities))
		self.assertAlmostEqual(row.features["trend"], average - before)
		self.assertEqual(row.features["failed_subjects"], sum(1 for s in scores.values() if s < 30))

	def test_labels_and_time_split(self):
		for row in self.rows[:50]:
			self.assertEqual(row.target, self.data.next(row.term).name)  # always the very next term
			result = frappe.db.get_value(
				"Student Term Result", {"student": row.student, "term": row.target}, ["division"], as_dict=True
			)
			failed = self.data.failed_subjects(row.student, row.target)
			self.assertEqual(row.label, int(result.division in ("Division IV", "Division 0") or failed >= 3))

		train, test = risk_model.split_by_time(self.rows, self.data)
		self.assertLess(
			max(self.data.index[r.target] for r in train), min(self.data.index[r.target] for r in test)
		)
		self.assertEqual({r.target for r in test}, {"Term 2 2025", "Term 3 2025"})
		self.assertGreaterEqual(len(train), risk_model.MIN_TRAIN_ROWS)

	def test_training_result_is_saved(self):
		doc = frappe.get_doc("Risk Model", self.model)
		self.assertIn(doc.status, ("Active", "Rejected"))
		self.assertEqual((doc.bootstrap_resamples, doc.bootstrap_seed), (1000, 42))
		self.assertLessEqual(doc.auc_difference_ci_low, doc.auc_difference_ci_high)
		self.assertEqual(doc.status, risk_model.decide(json.loads(doc.metrics_json))[0])
		self.assertEqual([c.feature for c in doc.coefficients], list(risk_model.FEATURES))

		details = json.loads(doc.metrics_json)
		self.assertEqual(len(details["model"]["calibration"]), 10)
		self.assertTrue(0 <= doc.brier_score <= 1)
		self.assertEqual(set(details["model"]["fairness"]["groups"]), {"Male", "Female"})
		self.assertEqual(details["bootstrap"]["unit"], "student")

		file = frappe.get_doc("File", {"file_url": doc.model_file})
		self.assertTrue(file.is_private)
		model = risk_model.load_model(self.model)
		self.assertEqual((model["features"], model["feature_set_version"]), (list(risk_model.FEATURES), 1))

	def test_decision_needs_a_clearly_better_auc_and_no_worse_precision(self):
		self.assertEqual(risk_model.decide(metrics(0.01, 0.5))[0], "Active")
		status, reason = risk_model.decide(metrics(-0.01, 0.6))
		self.assertEqual(status, "Rejected")
		self.assertIn("AUC is not clearly better", reason)
		status, reason = risk_model.decide(metrics(0.05, 0.4))
		self.assertEqual(status, "Rejected")
		self.assertIn("precision in the top 10% 40% against 50%", reason)

	def test_a_file_for_another_feature_set_is_refused(self):
		model = risk_model.load_model(self.model)
		for change in (
			{"features": list(reversed(model["features"]))},
			{"feature_set_version": 2},
			{"format": "something else"},
			{"coef": model["coef"][:-1]},
		):
			with self.subTest(change=change):
				self.assertRaises(frappe.ValidationError, risk_model.check_model, {**model, **change})

	def test_predictions_for_active_students_with_reasons(self):
		status = frappe.db.get_value("Risk Model", self.model, "status")
		self.addCleanup(frappe.db.set_value, "Risk Model", self.model, "status", status)
		frappe.db.set_value("Risk Model", self.model, "status", "Active")  # whatever the small school decided
		count = risk_model.refresh_predictions(feature_term="Term 3 2025")
		predictions = frappe.get_all(
			"Risk Prediction",
			filters={"feature_term": "Term 3 2025"},
			fields=["student", "term", "probability", "reasons", "rule_score", "risk_model"],
		)
		self.assertEqual(len(predictions), count)
		self.assertTrue(count)
		model = risk_model.load_model(self.model)
		for p in predictions:
			self.assertEqual(frappe.db.get_value("Student", p.student, "status"), "Active")
			self.assertTrue(0 <= p.probability <= 100)
			self.assertLessEqual(len(p.reasons.splitlines()), 3)
			features = self.data.features(p.student, self.data.terms[self.data.index["Term 3 2025"]])
			self.assertAlmostEqual(p.probability, round(risk_model.predict(model, features)[0] * 100, 1))

		# Gender plays no part; a student who leaves loses the prediction
		student = predictions[0].student
		before = predictions[0].probability
		frappe.db.set_value("Student", student, "gender", "Female" if self.data.gender[student] == "Male" else "Male")
		risk_model.refresh_predictions(feature_term="Term 3 2025")
		self.assertEqual(frappe.db.get_value("Risk Prediction", {"student": student}, "probability"), before)
		doc = frappe.get_doc("Student", student)
		doc.status = "Transferred"
		doc.save()
		risk_model.refresh_predictions(feature_term="Term 3 2025")
		self.assertFalse(frappe.db.exists("Risk Prediction", {"student": student}))

	def test_not_enough_data_keeps_the_rule_based_score(self):
		with patch.object(risk_model, "MIN_TRAIN_ROWS", 100_000):
			name = risk_model.train_model()
		doc = frappe.get_doc("Risk Model", name)
		self.assertEqual(doc.status, "Insufficient Data")
		self.assertFalse(doc.model_file)
		self.assertIn("rule-based risk score stays in use", doc.decision)

	def test_only_system_manager_trains_and_only_staff_read(self):
		with as_user(HEADMASTER), enforce_roles():
			self.assertRaises(frappe.PermissionError, call, "smart_school.risk_model.retrain")
		with patch("frappe.enqueue") as enqueue:
			call("smart_school.risk_model.retrain")
		self.assertEqual(enqueue.call_args.kwargs["job_id"], "smart_school_risk_model_training")

		self.assertTrue(frappe.has_permission("Risk Model", "read", doc=self.model, user=HEADMASTER))
		for user in (TEACHER_1, PARENT_1):
			self.assertFalse(frappe.has_permission("Risk Model", "read", doc=self.model, user=user))
			self.assertFalse(frappe.has_permission("Risk Prediction", "read", user=user))
