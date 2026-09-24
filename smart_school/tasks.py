import json

import frappe
from frappe.utils import flt, now_datetime, today

from smart_school.results import get_grade, get_subject_scores

# Level at which each risk part reaches its maximum (part = 1)
FULL_ABSENCE_RATE = 30  # % of recorded days
FULL_DISCIPLINE_POINTS = 8
FULL_FAILED_SUBJECTS = 3
FULL_DECLINE = 10  # average points
SEVERITY_POINTS = {"Minor": 1, "Moderate": 2, "Serious": 4}
INSIGHT_THRESHOLD = 5  # % change


def get_current_term():
	"""The latest term that has started."""
	term = frappe.get_all(
		"Term",
		filters={"start_date": ["<=", today()]},
		fields=["name", "start_date", "end_date"],
		order_by="start_date desc",
		limit=1,
	)
	return term[0] if term else None


def get_previous_term(term):
	previous = frappe.get_all(
		"Term",
		filters={"start_date": ["<", term.start_date]},
		pluck="name",
		order_by="start_date desc",
		limit=1,
	)
	return previous[0] if previous else None


# ---------- #20 risk score ----------


def calculate_all_risk_scores():
	term = get_current_term()
	if not term:
		return

	settings = frappe.get_cached_doc("Smart School Settings")
	for student in frappe.get_all("Student", filters={"status": "Active"}, pluck="name"):
		calculate_risk_score(student, term, settings)


def calculate_risk_score(student, term=None, settings=None):
	"""Risk score 0-100 for the current term: five parts scored 0-1, weighted from Smart School Settings.
	The breakdown is stored so the score can be explained."""
	term = term or get_current_term()
	settings = settings or frappe.get_cached_doc("Smart School Settings")
	if not term:
		return None

	parts = {}

	# Attendance: Absent counts fully, Late half, Excused not at all
	statuses = frappe.get_all("Attendance", filters={"student": student, "term": term.name}, pluck="status")
	absences = statuses.count("Absent") + 0.5 * statuses.count("Late")
	absence_rate = absences / len(statuses) * 100 if statuses else 0
	parts["attendance"] = {
		"days": len(statuses),
		"absent": statuses.count("Absent"),
		"late": statuses.count("Late"),
		"excused": statuses.count("Excused"),
		"rate": flt(absence_rate, 1),
		"part": min(absence_rate / FULL_ABSENCE_RATE, 1),
	}

	# Discipline in the term's dates, weighted by severity
	severities = frappe.get_all(
		"Discipline Record",
		filters={"student": student, "date": ["between", [term.start_date, term.end_date]]},
		pluck="severity",
	)
	points = sum(SEVERITY_POINTS.get(s, 0) for s in severities)
	parts["discipline"] = {
		"records": len(severities),
		"points": points,
		"part": min(points / FULL_DISCIPLINE_POINTS, 1),
	}

	# Results of the current term
	average = frappe.db.get_value("Student Term Result", {"student": student, "term": term.name}, "average")
	threshold = flt(settings.risk_average_threshold) or 45
	if average is None:
		parts["low_average"] = {"average": None, "part": 0}
		parts["failed_subjects"] = {"subjects": [], "part": 0}
		parts["decline"] = {"previous_average": None, "drop": 0, "part": 0}
	else:
		parts["low_average"] = {
			"average": flt(average, 2),
			"threshold": threshold,
			"part": min(max((threshold - flt(average)) / threshold, 0), 1),
		}

		scores = get_subject_scores(student, term.name)[0]
		failed = sorted(subject for subject, score in scores.items() if get_grade(score)[0] == "F")
		parts["failed_subjects"] = {"subjects": failed, "part": min(len(failed) / FULL_FAILED_SUBJECTS, 1)}

		previous_term = get_previous_term(term)
		previous_average = previous_term and frappe.db.get_value(
			"Student Term Result", {"student": student, "term": previous_term}, "average"
		)
		drop = max(flt(previous_average) - flt(average), 0) if previous_average is not None else 0
		parts["decline"] = {
			"previous_term": previous_term,
			"previous_average": previous_average,
			"drop": flt(drop, 2),
			"part": min(drop / FULL_DECLINE, 1),
		}

	weights = {
		"attendance": settings.risk_weight_attendance,
		"discipline": settings.risk_weight_discipline,
		"low_average": settings.risk_weight_low_average,
		"failed_subjects": settings.risk_weight_failed_subjects,
		"decline": settings.risk_weight_decline,
	}
	score = 0
	for key, part in parts.items():
		part["part"] = flt(part["part"], 3)
		part["weight"] = flt(weights[key])
		part["score"] = flt(part["part"] * part["weight"], 1)
		score += part["score"]
	score = flt(min(score, 100), 1)

	level = get_risk_level(score, settings)

	frappe.db.set_value(
		"Student",
		student,
		{
			"risk_score": score,
			"risk_level": level,
			"risk_breakdown": json.dumps({"term": term.name, **parts}, default=str, indent=1),
			"risk_updated_on": now_datetime(),
		},
		update_modified=False,
	)
	return score, level


def get_risk_level(score, settings):
	if score >= flt(settings.risk_high_from):
		return "High"
	if score >= flt(settings.risk_medium_from):
		return "Medium"
	return "Low"


# ---------- #21 performance insights ----------


def generate_performance_insights():
	for class_name in frappe.get_all("Class", pluck="name"):
		check_class_performance(class_name)


def check_class_performance(class_name):
	"""Compare the class (and each subject) between its two latest terms, ordered by start date.
	The class is taken from the term results, so promotions do not mix classes."""
	terms = frappe.db.sql(
		"""select str.term from `tabStudent Term Result` str join `tabTerm` t on t.name = str.term
        where str.class = %s group by str.term order by max(t.start_date) desc limit 2""",
		class_name,
		pluck=True,
	)
	if len(terms) < 2:
		return

	current_term, previous_term = terms
	current = get_class_term_scores(class_name, current_term)
	previous = get_class_term_scores(class_name, previous_term)

	save_insight(class_name, current_term, None, mean(current["averages"]), mean(previous["averages"]))
	for subject in sorted(set(current["subjects"]) & set(previous["subjects"])):
		save_insight(
			class_name,
			current_term,
			subject,
			mean(current["subjects"][subject]),
			mean(previous["subjects"][subject]),
		)


def get_class_term_scores(class_name, term):
	results = frappe.get_all(
		"Student Term Result", filters={"class": class_name, "term": term}, fields=["student", "average"]
	)
	subjects = {}
	for r in results:
		for subject, score in get_subject_scores(r.student, term)[0].items():
			subjects.setdefault(subject, []).append(score)
	return {"averages": [flt(r.average) for r in results], "subjects": subjects}


def mean(values):
	return sum(values) / len(values) if values else 0


def save_insight(class_name, term, subject, current_avg, previous_avg):
	"""Create or update the insight; a change below the threshold removes a stale one (derived data)."""
	existing = frappe.db.get_value(
		"Performance Insight",
		{"class": class_name, "term": term, "subject": subject or ["is", "not set"]},
		"name",
	)
	change = (current_avg - previous_avg) / previous_avg * 100 if previous_avg else 0

	if abs(change) < INSIGHT_THRESHOLD:
		if existing:
			frappe.delete_doc("Performance Insight", existing, ignore_permissions=True, force=True)
		return

	what = f"Wastani wa {subject}" if subject else "Ufaulu"
	direction = "umeshuka" if change < 0 else "umepanda"
	message = (
		f"{what} wa {class_name} {direction} kwa {abs(flt(change, 1))}% ukilinganisha na muhula uliopita."
	)

	doc = (
		frappe.get_doc("Performance Insight", existing) if existing else frappe.new_doc("Performance Insight")
	)
	doc.update(
		{
			"class": class_name,
			"term": term,
			"subject": subject,
			"message": message,
			"date_generated": today(),
			"change_percentage": flt(change, 1),
		}
	)
	doc.save(ignore_permissions=True)


# ---------- #22 academic records ----------


def create_academic_records_for_ended_years():
	"""Daily: for every academic year that has ended (end_date <= today), record each student's class
	and final result. Records that exist (e.g. from the Promotion Tool) are left alone."""
	for year in frappe.get_all("Academic Year", filters={"end_date": ["<=", today()]}, pluck="name"):
		for student in frappe.get_all(
			"Student", filters={"status": ["in", ["Active", "Graduated"]]}, pluck="name"
		):
			ensure_academic_record(student, year)
	frappe.db.commit()


def ensure_academic_record(student, academic_year, student_class=None):
	"""Create the Student Academic Record for this year if missing. The class comes from the last term
	result of the year, else the given / current class."""
	if frappe.db.exists("Student Academic Record", {"student": student, "academic_year": academic_year}):
		return None

	last = frappe.db.sql(
		"""select str.class, str.average, str.division, str.division_display
        from `tabStudent Term Result` str join `tabTerm` t on t.name = str.term
        where str.student = %s and t.academic_year = %s
        order by t.start_date desc limit 1""",
		(student, academic_year),
		as_dict=True,
	)
	last = last[0] if last else frappe._dict()

	record = frappe.new_doc("Student Academic Record")
	record.student = student
	record.academic_year = academic_year
	record.set(
		"class",
		last.get("class") or student_class or frappe.db.get_value("Student", student, "current_class"),
	)
	record.final_average = last.get("average")
	record.final_division = last.get("division_display") or last.get("division")
	record.insert(ignore_permissions=True)
	return record.name
