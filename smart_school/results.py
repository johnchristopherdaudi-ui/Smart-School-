from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe.utils import flt, now_datetime

BEST_SUBJECTS = 7
INCOMPLETE = "Incomplete"
PUBLISHER_ROLES = ("Headmaster", "System Manager")


def round_half_up(value):
	"""74.5 -> 75. Python's round() uses banker's rounding (round(74.5) == 74)."""
	return int(Decimal(str(flt(value))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def get_grade(score):
	"""Return (grade, points) for an integer score from the Grading System table."""
	row = frappe.get_all(
		"Grading System",
		filters={"minimum_mark": ["<=", score], "maximum_mark": [">=", score]},
		fields=["grade", "points"],
		limit=1,
	)
	if not row:
		frappe.throw(f"No grade in the Grading System covers a score of {score}")
	return row[0].grade, row[0].points


def get_division(total_points):
	row = frappe.get_all(
		"Division Grading",
		filters={"minimum_points": ["<=", total_points], "maximum_points": [">=", total_points]},
		fields=["division"],
		limit=1,
	)
	return row[0].division if row else ""


def validate_non_overlapping_range(doc, low_field, high_field, unique_fields=()):
	"""Grading System / Division Grading rows must not overlap, so every score maps to one row."""
	low, high = doc.get(low_field), doc.get(high_field)
	if low > high:
		frappe.throw(
			f"{doc.meta.get_label(low_field)} cannot be greater than {doc.meta.get_label(high_field)}"
		)

	overlap = frappe.get_all(
		doc.doctype,
		filters={"name": ["!=", doc.name], low_field: ["<=", high], high_field: [">=", low]},
		pluck="name",
	)
	if overlap:
		frappe.throw(f"The range {low}-{high} overlaps with {', '.join(overlap)}")

	for fieldname in unique_fields:
		other = frappe.db.get_value(
			doc.doctype, {fieldname: doc.get(fieldname), "name": ["!=", doc.name]}, "name"
		)
		if other:
			frappe.throw(f"{doc.meta.get_label(fieldname)} {doc.get(fieldname)} is already used by {other}")


def get_subject_scores(student, term):
	"""One integer score per subject: the weighted average of the percentages of the exams the student
	sat this term (plain average unless every one of those exams has a weight), rounded half up."""
	exams = {
		e.name: e for e in frappe.get_all("Exam", filters={"term": term}, fields=["name", "class", "weight"])
	}
	results = frappe.get_all(
		"Exam Result",
		filters={"student": student, "exam": ["in", list(exams) or [""]], "docstatus": 1},
		fields=["subject", "exam", "percentage"],
	)

	by_subject = {}
	for r in results:
		by_subject.setdefault(r.subject, []).append((flt(r.percentage), flt(exams[r.exam].weight)))

	scores = {}
	for subject, rows in by_subject.items():
		if all(weight > 0 for _, weight in rows):
			average = sum(p * w for p, w in rows) / sum(w for _, w in rows)
		else:
			average = sum(p for p, _ in rows) / len(rows)
		scores[subject] = round_half_up(average)

	exam_class = exams[results[0].exam]["class"] if results else None
	return scores, exam_class


def recompute_student_term_result(student, term):
	scores, exam_class = get_subject_scores(student, term)
	existing = frappe.db.get_value("Student Term Result", {"student": student, "term": term}, "name")

	if not scores:
		# Derived record: nothing submitted remains for this term
		if existing:
			frappe.delete_doc("Student Term Result", existing, ignore_permissions=True, force=True)
		return None

	points = sorted(get_grade(score)[1] for score in scores.values())
	if len(points) < BEST_SUBJECTS:
		division, total_points, division_display = INCOMPLETE, 0, INCOMPLETE
	else:
		total_points = sum(points[:BEST_SUBJECTS])
		division = get_division(total_points)
		division_display = f"{division}, Points {total_points}" if division else ""

	doc = (
		frappe.get_doc("Student Term Result", existing) if existing else frappe.new_doc("Student Term Result")
	)
	doc.update(
		{
			"student": student,
			"term": term,
			"class": exam_class,
			"academic_year": frappe.get_cached_value("Term", term, "academic_year"),
			"average": flt(sum(scores.values()) / len(scores), 2),
			"subjects_count": len(scores),
			"total_points": total_points,
			"division": division,
			"division_display": division_display,
		}
	)
	doc.flags.recompute = True
	doc.save(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def recompute_term_results(exam):
	frappe.only_for(PUBLISHER_ROLES)
	term = frappe.get_value("Exam", exam, "term")
	students = frappe.get_all(
		"Exam Result", filters={"exam": exam, "docstatus": 1}, pluck="student", distinct=True
	)
	for student in students:
		recompute_student_term_result(student, term)
	return len(students)


@frappe.whitelist()
def publish_exam_results(exam):
	frappe.only_for(PUBLISHER_ROLES)
	doc = frappe.get_doc("Exam", exam)
	if doc.results_published:
		frappe.throw("Results for this exam are already published")

	weights = frappe.get_all("Exam", filters={"class": doc.get("class"), "term": doc.term}, pluck="weight")
	if any(weights) and flt(sum(flt(w) for w in weights), 2) != 100:
		frappe.throw(
			f"Weights of {doc.get('class')} exams in {doc.term} add up to {sum(flt(w) for w in weights):g}; "
			"they must add up to 100 before results are published"
		)

	doc.db_set({"results_published": 1, "published_on": now_datetime()})
	frappe.enqueue("smart_school.results.notify_published_exam", exam=exam, enqueue_after_commit=True)


@frappe.whitelist()
def unpublish_exam_results(exam):
	frappe.only_for(PUBLISHER_ROLES)
	frappe.get_doc("Exam", exam).db_set({"results_published": 0, "published_on": None})


def notify_published_exam(exam):
	"""One message per student for a published exam, instead of one per subject."""
	from smart_school.notifications import send_notification

	exam_doc = frappe.get_doc("Exam", exam)
	results = frappe.get_all(
		"Exam Result",
		filters={"exam": exam, "docstatus": 1},
		fields=["student", "subject", "marks", "grade"],
		order_by="subject asc",
	)
	by_student = {}
	for r in results:
		by_student.setdefault(r.student, []).append(r)

	for student, rows in by_student.items():
		student_name = frappe.db.get_value("Student", student, "full_name")
		marks = ", ".join(
			f"{r.subject} {flt(r.marks):g}/{flt(exam_doc.max_marks):g} ({r.grade})" for r in rows
		)
		send_notification(student, f"Matokeo ya {exam_doc.exam_name} kwa {student_name}: {marks}", "Matokeo")


def is_term_summary_published(term, class_name):
	"""Parents see the term average / division only when every exam of that term for the class is published."""
	exams = frappe.get_all("Exam", filters={"term": term, "class": class_name}, pluck="results_published")
	return bool(exams) and all(exams)


def get_portal_results(student):
	"""What a parent may see, per term (oldest first): marks of published exams only, and the term
	summary only when every exam of that term for the class is published."""
	exams = {
		e.name: e
		for e in frappe.get_all(
			"Exam",
			filters={"results_published": 1},
			fields=["name", "exam_name", "term", "class", "max_marks"],
		)
	}
	rows = frappe.get_all(
		"Exam Result",
		filters={"student": student, "exam": ["in", list(exams) or [""]], "docstatus": 1},
		fields=["exam", "subject", "marks", "grade"],
		order_by="subject asc",
	)
	summaries = {
		s.term: s
		for s in frappe.get_all(
			"Student Term Result",
			filters={"student": student},
			fields=[
				"term",
				"class",
				"average",
				"division",
				"division_display",
				"total_points",
				"subjects_count",
			],
		)
	}

	terms = {}
	for r in rows:
		exam = exams[r.exam]
		term = terms.setdefault(exam.term, frappe._dict(term=exam.term, subjects=[], summary=None))
		term.subjects.append(
			frappe._dict(
				exam_name=exam.exam_name,
				subject=r.subject,
				marks=flt(r.marks),
				max_marks=flt(exam.max_marks),
				grade=r.grade,
			)
		)

	for term in terms.values():
		summary = summaries.get(term.term)
		if summary and is_term_summary_published(term.term, summary["class"]):
			summary.average = flt(summary.average, 1)
			term.summary = summary
		term.update(frappe.get_cached_value("Term", term.term, ["term_name", "start_date"], as_dict=True))

	return sorted(terms.values(), key=lambda t: t.start_date)


def get_class_positions(class_name, term):
	"""Standard competition ranking by term average (1, 2, 2, 4) of the students with a division.
	Students marked Incomplete get no position. Returns ({student: position}, ranked_results)."""
	results = frappe.get_all(
		"Student Term Result",
		filters={"class": class_name, "term": term, "division": ["!=", INCOMPLETE]},
		fields=["student", "average", "subjects_count", "total_points", "division", "division_display"],
	)
	ranked = sorted(results, key=lambda r: -flt(r.average, 2))
	positions, position, previous = {}, 0, None
	for i, r in enumerate(ranked, start=1):
		if flt(r.average, 2) != previous:
			position, previous = i, flt(r.average, 2)
		positions[r.student] = position
	return positions, ranked
