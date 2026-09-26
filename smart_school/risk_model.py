"""Early-warning model: the chance that a student is at risk next term (Division IV/0, or 3+ subjects with F),
from the results, attendance and discipline of the term that has just ended.

A logistic regression is trained on past student-terms (students who have left count too) and tested on the
most recent terms against the rule-based risk score. It becomes Active only when it is clearly better: the
lower end of the bootstrap 95% interval of (model AUC - rule AUC) is above 0, and its precision among the 10%
of students it ranks highest is not lower. Otherwise the rule-based score stays in use.

The model is kept as a private JSON file (ordered features, feature set version, scaler, coefficients), never a
pickle; a file made for another feature set is refused. scikit-learn is only needed to train: predictions are
computed from the file. Gender is never a feature; it is only used to compare fairness."""

import json
import math
from bisect import bisect_right

import frappe
from frappe.utils import cint, flt, getdate, now_datetime, today

from smart_school.results import INCOMPLETE, get_grade, get_subject_scores
from smart_school.tasks import SEVERITY_POINTS, get_risk_score

MODEL_FORMAT = "smart_school.risk_model"
FEATURE_SET_VERSION = 1
FEATURES = ("average", "trend", "no_previous_term", "failed_subjects", "absence_rate", "discipline_points")

MIN_TRAIN_ROWS = 200
MIN_TRAIN_POSITIVES = 20
TEST_TERMS = 2
TOP_SHARE = 0.10
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 42
FAIRNESS_GAP = 0.10
FAILED_SUBJECTS_AT_RISK = 3
TRAINER_ROLES = ("System Manager",)


# ---------- data ----------


class SchoolData:
	"""Everything the features and labels need, loaded once."""

	def __init__(self):
		self.terms = frappe.get_all("Term", fields=["name", "start_date", "end_date"], order_by="start_date asc")
		self.index = {t.name: i for i, t in enumerate(self.terms)}
		self.at_risk_divisions = set(
			frappe.get_all("Division Grading", pluck="division", order_by="minimum_points desc", limit=2)
		)
		self.results = {
			(r.student, r.term): r
			for r in frappe.get_all(
				"Student Term Result", fields=["student", "term", "average", "division", "class"]
			)
		}
		self.attendance = {}
		for r in frappe.db.sql(
			"""select student, term, status, count(*) as days from `tabAttendance`
			where ifnull(term, '') != '' group by student, term, status""",
			as_dict=True,
		):
			self.attendance.setdefault((r.student, r.term), {})[r.status] = r.days

		starts = [getdate(t.start_date) for t in self.terms]
		self.discipline = {}
		for r in frappe.get_all("Discipline Record", fields=["student", "date", "severity"]):
			i = bisect_right(starts, getdate(r.date)) - 1
			if i >= 0 and getdate(r.date) <= getdate(self.terms[i].end_date):
				key = (r.student, self.terms[i].name)
				self.discipline[key] = self.discipline.get(key, 0) + SEVERITY_POINTS.get(r.severity, 0)

		self.gender = dict(frappe.get_all("Student", fields=["name", "gender"], as_list=True))
		self._failed, self._grades = {}, {}

	def finished_terms(self):
		return [t for t in self.terms if getdate(t.end_date) < getdate(today())]

	def previous(self, term):
		i = self.index[term.name]
		return self.terms[i - 1] if i else None

	def next(self, term):
		i = self.index[term.name]
		return self.terms[i + 1] if i + 1 < len(self.terms) else None

	def failed_subjects(self, student, term):
		key = (student, term)
		if key not in self._failed:
			scores = get_subject_scores(student, term)[0]
			self._failed[key] = sum(1 for score in scores.values() if self.grade(score) == "F")
		return self._failed[key]

	def grade(self, score):
		if score not in self._grades:
			self._grades[score] = get_grade(score)[0]
		return self._grades[score]

	def features(self, student, term):
		"""The features of one student in one term (None without a term result). Absent counts fully,
		Late half, Excused not at all; discipline is weighted by severity."""
		result = self.results.get((student, term.name))
		if not result:
			return None
		previous_term = self.previous(term)
		previous = previous_term and self.results.get((student, previous_term.name))
		days = self.attendance.get((student, term.name), {})
		total = sum(days.values())
		missed = days.get("Absent", 0) + 0.5 * days.get("Late", 0)
		return {
			"average": flt(result.average),
			"trend": flt(result.average) - flt(previous.average) if previous else 0.0,
			"no_previous_term": 0 if previous else 1,
			"failed_subjects": self.failed_subjects(student, term.name),
			"absence_rate": missed / total if total else 0.0,
			"discipline_points": self.discipline.get((student, term.name), 0),
		}

	def label(self, student, term):
		"""1 when the term ended in Division IV/0 or with 3+ subjects with F; None when it is Incomplete."""
		result = self.results.get((student, term.name))
		if not result or result.division == INCOMPLETE:
			return None
		at_risk = result.division in self.at_risk_divisions
		return int(at_risk or self.failed_subjects(student, term.name) >= FAILED_SUBJECTS_AT_RISK)


def build_rows(data):
	"""One row per student and pair of consecutive finished terms: features of the first, label of the next."""
	rows = []
	finished = {t.name for t in data.finished_terms()}
	students_by_term = {}
	for student, term_name in data.results:
		students_by_term.setdefault(term_name, []).append(student)
	for term in data.terms:
		target = data.next(term)
		if term.name not in finished or not target or target.name not in finished:
			continue
		for student in students_by_term.get(term.name, []):
			label = data.label(student, target)
			if label is None:
				continue
			rows.append(
				frappe._dict(
					student=student,
					term=term,
					target=target.name,
					features=data.features(student, term),
					label=label,
					gender=data.gender.get(student),
				)
			)
	return sorted(rows, key=lambda r: (data.index[r.target], r.student))


def split_by_time(rows, data):
	"""The most recent TEST_TERMS target terms are the test set; everything before them trains."""
	targets = sorted({r.target for r in rows}, key=lambda t: data.index[t])
	test_targets = set(targets[-TEST_TERMS:])
	return [r for r in rows if r.target not in test_targets], [r for r in rows if r.target in test_targets]


# ---------- the model file ----------


def fit(rows):
	import numpy as np
	import sklearn
	from sklearn.linear_model import LogisticRegression
	from sklearn.preprocessing import StandardScaler

	x = np.array([[r.features[f] for f in FEATURES] for r in rows], dtype=float)
	y = np.array([r.label for r in rows])
	scaler = StandardScaler().fit(x)
	regression = LogisticRegression(C=1.0, max_iter=1000).fit(scaler.transform(x), y)
	return {
		"format": MODEL_FORMAT,
		"feature_set_version": FEATURE_SET_VERSION,
		"features": list(FEATURES),
		"mean": scaler.mean_.tolist(),
		"scale": scaler.scale_.tolist(),
		"coef": regression.coef_[0].tolist(),
		"intercept": float(regression.intercept_[0]),
		"trained_rows": len(rows),
		"sklearn_version": sklearn.__version__,
	}


def check_model(model):
	"""Refuse a model made for another feature set: the features must match in name, order and version."""
	if not isinstance(model, dict) or model.get("format") != MODEL_FORMAT:
		frappe.throw("This file is not a Smart School risk model")
	if model.get("feature_set_version") != FEATURE_SET_VERSION or model.get("features") != list(FEATURES):
		frappe.throw(
			f"This model was trained with feature set version {model.get('feature_set_version')} "
			f"({', '.join(model.get('features') or [])}); the app uses version {FEATURE_SET_VERSION} "
			f"({', '.join(FEATURES)}). Train the model again."
		)
	if not all(len(model.get(k) or []) == len(FEATURES) for k in ("mean", "scale", "coef")):
		frappe.throw("The risk model file is damaged: the numbers do not match the features")
	return model


def load_model(risk_model):
	file_url = frappe.db.get_value("Risk Model", risk_model, "model_file")
	if not file_url:
		frappe.throw(f"{risk_model} has no model file")
	content = frappe.get_doc("File", {"file_url": file_url}).get_content()
	return check_model(json.loads(content))


def predict(model, features):
	"""(probability, {feature: contribution}). A contribution is the coefficient times the standardised value,
	so a positive one raises the risk compared with an average student."""
	z = model["intercept"]
	contributions = {}
	for name, mean, scale, coef in zip(model["features"], model["mean"], model["scale"], model["coef"]):
		contributions[name] = coef * (features[name] - mean) / (scale or 1)
		z += contributions[name]
	probability = 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
	return probability, contributions


REASONS = {
	"average": lambda v, m: f"Average of {v:.0f}% (school average {m:.0f}%)",
	"trend": lambda v, m: f"Average fell by {-v:.0f} points since the term before"
	if v < 0
	else f"Average changed by {v:+.0f} points since the term before",
	"no_previous_term": lambda v, m: "No results from the term before to compare with",
	"failed_subjects": lambda v, m: f"{v:.0f} subject(s) with F",
	"absence_rate": lambda v, m: f"Missed {v:.0%} of school days, late arrivals counted as half "
	f"(school average {m:.0%})",
	"discipline_points": lambda v, m: f"Discipline incidents worth {v:g} points (Minor 1, Moderate 2, Serious 4)",
}


def explain(model, features, contributions, top=3):
	"""The (up to) three features that raise this student's risk most, in plain words."""
	means = dict(zip(model["features"], model["mean"]))
	raising = sorted((c, name) for name, c in contributions.items() if c > 0)[::-1][:top]
	return [REASONS[name](features[name], means[name]) for _, name in raising]


# ---------- evaluation ----------


def flag_top(rows, scores, share=TOP_SHARE):
	"""Within each target term, flag the highest-scoring share of students (ties broken by student)."""
	flags = [False] * len(rows)
	by_term = {}
	for i, r in enumerate(rows):
		by_term.setdefault(r.target, []).append(i)
	for indexes in by_term.values():
		ranked = sorted(indexes, key=lambda i: (-scores[i], rows[i].student))
		for i in ranked[: max(1, math.ceil(len(indexes) * share))]:
			flags[i] = True
	return flags


def confusion(labels, flags):
	tp = sum(1 for y, f in zip(labels, flags) if y and f)
	fp = sum(1 for y, f in zip(labels, flags) if not y and f)
	fn = sum(1 for y, f in zip(labels, flags) if y and not f)
	return {"tp": tp, "fp": fp, "fn": fn, "tn": len(labels) - tp - fp - fn}


def precision_recall(labels, flags):
	c = confusion(labels, flags)
	flagged, positives = c["tp"] + c["fp"], c["tp"] + c["fn"]
	return (c["tp"] / flagged if flagged else 0.0), (c["tp"] / positives if positives else 0.0)


def calibration(labels, probabilities, bins=10):
	"""Predicted against observed rate in ten equal-sized groups, from the lowest predictions up."""
	order = sorted(range(len(labels)), key=lambda i: probabilities[i])
	groups = []
	for b in range(bins):
		part = order[len(order) * b // bins : len(order) * (b + 1) // bins]
		if part:
			groups.append(
				{
					"decile": b + 1,
					"students": len(part),
					"mean_predicted": round(sum(probabilities[i] for i in part) / len(part), 4),
					"observed": round(sum(labels[i] for i in part) / len(part), 4),
				}
			)
	return groups


def bootstrap_auc_difference(rows, labels, model_scores, rule_scores):
	"""95% interval of (model AUC - rule AUC). Students are resampled, not rows: a student appears in
	several test terms and those rows are not independent."""
	import numpy as np
	from sklearn.metrics import roc_auc_score

	y, m, r = np.array(labels), np.array(model_scores), np.array(rule_scores)
	students = sorted({row.student for row in rows})
	rows_of = {s: [] for s in students}
	for i, row in enumerate(rows):
		rows_of[row.student].append(i)
	rows_of = [np.array(rows_of[s]) for s in students]

	rng = np.random.default_rng(BOOTSTRAP_SEED)
	differences = []
	for _ in range(BOOTSTRAP_RESAMPLES):
		picked = np.concatenate([rows_of[k] for k in rng.integers(0, len(students), len(students))])
		if y[picked].min() == y[picked].max():
			continue  # AUC needs both outcomes
		differences.append(roc_auc_score(y[picked], m[picked]) - roc_auc_score(y[picked], r[picked]))
	low, high = np.percentile(differences, [2.5, 97.5])
	return {
		"resamples": BOOTSTRAP_RESAMPLES,
		"used": len(differences),
		"seed": BOOTSTRAP_SEED,
		"unit": "student",
		"mean_difference": float(np.mean(differences)),
		"ci_low": float(low),
		"ci_high": float(high),
	}


def fairness(rows, labels, flags):
	groups = {}
	for gender in sorted({r.gender for r in rows if r.gender}):
		idx = [i for i, r in enumerate(rows) if r.gender == gender]
		group_labels = [labels[i] for i in idx]
		group_flags = [flags[i] for i in idx]
		precision, recall = precision_recall(group_labels, group_flags)
		groups[gender] = {
			"students": len(idx),
			"positives": sum(group_labels),
			"flagged": sum(group_flags),
			"precision": round(precision, 4),
			"recall": round(recall, 4),
		}
	result = {"groups": groups}
	if len(groups) == 2:
		a, b = groups.values()
		result["precision_gap"] = round(abs(a["precision"] - b["precision"]), 4)
		result["recall_gap"] = round(abs(a["recall"] - b["recall"]), 4)
		result["warning"] = max(result["precision_gap"], result["recall_gap"]) > FAIRNESS_GAP
	return result


def evaluate(test, model, data):
	from sklearn.metrics import brier_score_loss, roc_auc_score

	settings = frappe.get_cached_doc("Smart School Settings")
	labels = [r.label for r in test]
	probabilities = [predict(model, r.features)[0] for r in test]
	rule_scores = [get_risk_score(r.student, r.term, settings)[0] for r in test]

	model_flags, rule_flags = flag_top(test, probabilities), flag_top(test, rule_scores)
	model_precision, model_recall = precision_recall(labels, model_flags)
	rule_precision, rule_recall = precision_recall(labels, rule_flags)
	return {
		"top_share": TOP_SHARE,
		"base_rate": sum(labels) / len(labels),
		"model": {
			"auc": roc_auc_score(labels, probabilities),
			"precision_top": model_precision,
			"recall_top": model_recall,
			"confusion_top": confusion(labels, model_flags),
			"confusion_at_half": confusion(labels, [p >= 0.5 for p in probabilities]),
			"brier": brier_score_loss(labels, probabilities),
			"calibration": calibration(labels, probabilities),
			"fairness": fairness(test, labels, model_flags),
		},
		"rule": {
			"auc": roc_auc_score(labels, rule_scores),
			"precision_top": rule_precision,
			"recall_top": rule_recall,
			"confusion_top": confusion(labels, rule_flags),
			"fairness": fairness(test, labels, rule_flags),
		},
		"bootstrap": bootstrap_auc_difference(test, labels, probabilities, rule_scores),
	}


def decide(metrics):
	"""(status, reason): Active only when the AUC is better beyond doubt and the top-10% precision is not lower."""
	ci = metrics["bootstrap"]
	model, rule = metrics["model"], metrics["rule"]
	auc_text = (
		f"AUC {model['auc']:.3f} against {rule['auc']:.3f} "
		f"(difference 95% CI {ci['ci_low']:+.3f} to {ci['ci_high']:+.3f})"
	)
	precision_text = (
		f"precision in the top 10% {model['precision_top']:.0%} against {rule['precision_top']:.0%}"
	)
	better_auc = ci["ci_low"] > 0
	precision_ok = model["precision_top"] >= rule["precision_top"]
	if better_auc and precision_ok:
		return "Active", f"The model is better than the rule-based score: {auc_text}; {precision_text}."
	why = []
	if not better_auc:
		why.append(f"its AUC is not clearly better ({auc_text})")
	if not precision_ok:
		why.append(f"its {precision_text}")
	return "Rejected", "The rule-based score stays in use: " + " and ".join(why) + "."


# ---------- training and predictions ----------


@frappe.whitelist()
def retrain():
	"""Train now, in the background (System Manager only)."""
	frappe.only_for(TRAINER_ROLES)
	frappe.enqueue(
		"smart_school.risk_model.train_model",
		queue="long",
		timeout=3600,
		job_id="smart_school_risk_model_training",
		deduplicate=True,
		trained_by=frappe.session.user,
	)
	return "Training started. The new Risk Model appears in the list when it is done."


def train_model(trained_by=None):
	"""Weekly and on demand: build the data, test against the rule-based score, save a Risk Model."""
	data = SchoolData()
	rows = build_rows(data)
	train, test = split_by_time(rows, data)
	doc = frappe.new_doc("Risk Model")
	doc.update(
		{
			"trained_on": now_datetime(),
			"trained_by": trained_by or frappe.session.user,
			"feature_set_version": FEATURE_SET_VERSION,
			"features": ", ".join(FEATURES),
			"train_terms": term_range(train, data),
			"train_rows": len(train),
			"train_positives": sum(r.label for r in train),
			"test_terms": term_range(test, data),
			"test_rows": len(test),
			"test_positives": sum(r.label for r in test),
		}
	)

	problem = data_problem(train, test)
	if problem:
		doc.status = "Insufficient Data"
		doc.decision = f"{problem} The rule-based risk score stays in use."
		doc.insert(ignore_permissions=True)
		return doc.name

	metrics = evaluate(test, fit(train), data)
	doc.status, doc.decision = decide(metrics)
	final = fit(train + test)  # the model in use learns from every term, the test result is kept
	doc.update(
		{
			"final_rows": len(train + test),
			"model_auc": metrics["model"]["auc"],
			"rule_auc": metrics["rule"]["auc"],
			"auc_difference": metrics["model"]["auc"] - metrics["rule"]["auc"],
			"auc_difference_ci_low": metrics["bootstrap"]["ci_low"],
			"auc_difference_ci_high": metrics["bootstrap"]["ci_high"],
			"bootstrap_resamples": metrics["bootstrap"]["resamples"],
			"bootstrap_seed": metrics["bootstrap"]["seed"],
			"model_precision_top": metrics["model"]["precision_top"] * 100,
			"rule_precision_top": metrics["rule"]["precision_top"] * 100,
			"model_recall_top": metrics["model"]["recall_top"] * 100,
			"rule_recall_top": metrics["rule"]["recall_top"] * 100,
			"brier_score": metrics["model"]["brier"],
			"base_rate": metrics["base_rate"] * 100,
			"metrics_json": json.dumps(metrics, indent=1, default=float),
			"intercept": final["intercept"],
			"coefficients": [
				{"feature": name, "coefficient": coef, "mean": mean, "scale": scale}
				for name, coef, mean, scale in zip(FEATURES, final["coef"], final["mean"], final["scale"])
			],
		}
	)
	doc.insert(ignore_permissions=True)
	save_model_file(doc, final)

	if doc.status == "Active":
		for other in frappe.get_all(
			"Risk Model", filters={"status": "Active", "name": ["!=", doc.name]}, pluck="name"
		):
			frappe.db.set_value("Risk Model", other, "status", "Retired")
		refresh_predictions()
	return doc.name


def data_problem(train, test):
	if len(train) < MIN_TRAIN_ROWS or sum(r.label for r in train) < MIN_TRAIN_POSITIVES:
		return (
			f"Not enough data to train: {len(train)} student-terms with {sum(r.label for r in train)} at risk "
			f"(at least {MIN_TRAIN_ROWS} and {MIN_TRAIN_POSITIVES} are needed)."
		)
	if len({r.label for r in test}) < 2:
		return "The test terms do not have both outcomes, so the model cannot be compared."
	return None


def term_range(rows, data):
	targets = sorted({r.target for r in rows}, key=lambda t: data.index[t])
	return f"{targets[0]} to {targets[-1]}" if targets else ""


def save_model_file(doc, model):
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{doc.name}.json",
			"attached_to_doctype": "Risk Model",
			"attached_to_name": doc.name,
			"attached_to_field": "model_file",
			"is_private": 1,
			"content": json.dumps(model, indent=1),
		}
	).insert(ignore_permissions=True)
	doc.db_set("model_file", file.file_url)


def get_active_model():
	return frappe.db.get_value("Risk Model", {"status": "Active"}, "name", order_by="trained_on desc")


def refresh_predictions(feature_term=None):
	"""Daily and after training: with an Active model, predict the next term of every Active student from the
	latest finished term. Students who left are not predicted."""
	risk_model = get_active_model()
	if not risk_model:
		return 0
	model = load_model(risk_model)
	data = SchoolData()
	term = next((t for t in data.terms if t.name == feature_term), None) if feature_term else None
	term = term or (data.finished_terms() or [None])[-1]
	target = term and data.next(term)
	if not target:
		return 0

	settings = frappe.get_cached_doc("Smart School Settings")
	predicted = set()
	for student in frappe.get_all("Student", filters={"status": "Active"}, pluck="name"):
		features = data.features(student, term)
		if not features:
			continue
		probability, contributions = predict(model, features)
		rule_score, rule_level, _ = get_risk_score(student, term, settings)
		values = {
			"class": data.results[(student, term.name)]["class"],
			"feature_term": term.name,
			"probability": round(probability * 100, 1),
			"reasons": "\n".join(explain(model, features, contributions)),
			"contributions": json.dumps({k: round(v, 4) for k, v in contributions.items()}),
			"rule_score": rule_score,
			"rule_level": rule_level,
			"risk_model": risk_model,
		}
		name = frappe.db.get_value("Risk Prediction", {"student": student, "term": target.name}, "name")
		doc = frappe.get_doc("Risk Prediction", name) if name else frappe.new_doc("Risk Prediction")
		doc.update({"student": student, "term": target.name, **values})
		doc.save(ignore_permissions=True)
		predicted.add(student)

	for name in frappe.get_all(
		"Risk Prediction",
		filters={"term": target.name, "student": ["not in", list(predicted) or [""]]},
		pluck="name",
	):
		frappe.delete_doc("Risk Prediction", name, ignore_permissions=True, force=True)
	return len(predicted)
