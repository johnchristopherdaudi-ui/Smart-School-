import frappe


def calculate_all_risk_scores():
    students = frappe.get_all("Student", filters={"status": "Active"}, pluck="name")

    for student in students:
        calculate_risk_score(student)


def calculate_risk_score(student):
    score = 0

    term_results = frappe.get_all(
        "Student Term Result",
        filters={"student": student},
        fields=["average"],
        order_by="creation desc",
        limit_page_length=2
    )

    if len(term_results) >= 1:
        latest_average = term_results[0].average or 0
        if latest_average < 40:
            score += 40
        elif latest_average < 50:
            score += 25
        elif latest_average < 60:
            score += 10

    if len(term_results) >= 2:
        previous_average = term_results[1].average or 0
        latest_average = term_results[0].average or 0
        if latest_average < previous_average:
            score += 15

    discipline_count = frappe.db.count("Discipline Record", filters={"student": student})
    score += min(discipline_count * 10, 30)

    total_attendance = frappe.db.count("Attendance", filters={"student": student})
    absent_count = frappe.db.count("Attendance", filters={"student": student, "status": "Absent"})

    if total_attendance > 0:
        absent_rate = (absent_count / total_attendance) * 100
        if absent_rate > 30:
            score += 20
        elif absent_rate > 15:
            score += 10

    frappe.db.set_value("Student", student, "risk_score", score)


def generate_performance_insights():
    classes = frappe.get_all("Class", pluck="name")

    for class_name in classes:
        check_class_performance(class_name)


def check_class_performance(class_name):
    students = frappe.get_all("Student", filters={"current_class": class_name}, pluck="name")

    if not students:
        return

    terms_with_data = frappe.get_all(
        "Student Term Result",
        filters={"student": ["in", students]},
        fields=["term"],
        group_by="term",
        order_by="creation desc"
    )

    distinct_terms = []
    for row in terms_with_data:
        if row.term not in distinct_terms:
            distinct_terms.append(row.term)

    if len(distinct_terms) < 2:
        return

    current_term = distinct_terms[0]
    previous_term = distinct_terms[1]

    current_results = frappe.get_all(
        "Student Term Result",
        filters={"student": ["in", students], "term": current_term},
        fields=["average"]
    )

    previous_results = frappe.get_all(
        "Student Term Result",
        filters={"student": ["in", students], "term": previous_term},
        fields=["average"]
    )

    if not current_results or not previous_results:
        return

    current_avg = sum([r.average or 0 for r in current_results]) / len(current_results)
    previous_avg = sum([r.average or 0 for r in previous_results]) / len(previous_results)

    if previous_avg == 0:
        return

    change_percentage = ((current_avg - previous_avg) / previous_avg) * 100

    if abs(change_percentage) < 5:
        return

    if change_percentage < 0:
        message = f"{class_name} performance dropped {abs(round(change_percentage, 1))}% compared to previous term."
    else:
        message = f"{class_name} performance improved {round(change_percentage, 1)}% compared to previous term."

    existing = frappe.get_all(
        "Performance Insight",
        filters={"class": class_name, "term": current_term}
    )

    if not existing:
        frappe.get_doc({
            "doctype": "Performance Insight",
            "class": class_name,
            "term": current_term,
            "message": message,
            "date_generated": frappe.utils.today(),
            "change_percentage": round(change_percentage, 1)
        }).insert(ignore_permissions=True)

def create_academic_records_for_ended_years():
    """Inaendesha kila siku. Ikiwa Academic Year imeisha leo, unda
    Student Academic Record kwa kila mwanafunzi Active."""

    ended_years = frappe.get_all(
        "Academic Year",
        filters={"end_date": frappe.utils.today()},
        fields=["name"]
    )

    for year in ended_years:
        active_students = frappe.get_all(
            "Student",
            filters={"status": "Active"},
            fields=["name", "current_class"]
        )

        for student in active_students:
            exists = frappe.db.exists("Student Academic Record", {
                "student": student.name,
                "academic_year": year.name
            })
            if exists:
                continue

            terms_this_year = frappe.get_all(
                "Term",
                filters={"academic_year": year.name},
                fields=["name"],
                order_by="end_date desc",
                limit=1
            )

            final_average = None
            final_division = None
            if terms_this_year:
                last_term_result = frappe.get_all(
                    "Student Term Result",
                    filters={"student": student.name, "term": terms_this_year[0].name},
                    fields=["average", "division_display", "division"],
                    limit=1
                )
                if last_term_result:
                    final_average = last_term_result[0].average
                    final_division = last_term_result[0].division_display or last_term_result[0].division

            record = frappe.new_doc("Student Academic Record")
            record.student = student.name
            record.academic_year = year.name
            record.set("class", student.current_class)
            record.final_average = final_average
            record.final_division = final_division
            record.insert(ignore_permissions=True)

        frappe.db.commit()
        frappe.logger().info(f"Student Academic Records created for {year.name}")
