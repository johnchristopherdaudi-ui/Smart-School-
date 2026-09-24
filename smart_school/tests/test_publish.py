"""#12, #15, D4: publishing exams, what parents see, and one notification per student."""

from unittest.mock import patch

import frappe

from smart_school import results
from smart_school.results import get_portal_results
from smart_school.tests.factory import (
    HEADMASTER, PARENT_1, TEACHER_1, SchoolTestCase, add_result, as_user, call, make_exam, render,
)

PUBLISH = "smart_school.results.publish_exam_results"


class TestPublishing(SchoolTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mid = make_exam("_Test Pub Mid", "_Test T1", "_Test FORM 1", weight=40)
        cls.final = make_exam("_Test Pub Final", "_Test T1", "_Test FORM 1", weight=60)
        for student in (cls.s["a"], cls.s["b"]):
            for subject in ("_T MATH", "_T ENGLISH"):
                add_result(student, cls.mid, subject, 60)
                add_result(student, cls.final, subject, 60)

    def publish(self, exam, user=HEADMASTER):
        with as_user(user), patch("frappe.enqueue") as enqueue:
            call(PUBLISH, exam=exam)
        return enqueue

    def test_only_headmaster_or_system_manager_publish(self):
        for user in (PARENT_1, TEACHER_1):
            self.assertRaises(frappe.PermissionError, self.publish, self.mid, user)

    def test_parent_sees_published_exams_only_and_summary_when_all_published(self):
        with as_user(PARENT_1):
            self.assertEqual([t.term for t in get_portal_results(self.s["a"])], [])

        enqueue = self.publish(self.mid)
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.kwargs["exam"], self.mid)
        self.assertRaises(frappe.ValidationError, self.publish, self.mid)  # already published

        with as_user(PARENT_1):
            term = get_portal_results(self.s["a"])[0]
            self.assertEqual({s.exam_name for s in term.subjects}, {"_Test Pub Mid"})
            self.assertIsNone(term.summary)
            status, body, _ = render("parent-portal/results", student=self.s["a"])
            self.assertIn("_Test Pub Mid", body)
            self.assertNotIn("_Test Pub Final", body)

        self.publish(self.final)
        with as_user(PARENT_1):
            self.assertIsNotNone(get_portal_results(self.s["a"])[0].summary)

    def test_publish_requires_weights_to_add_up(self):
        exam = make_exam("_Test Pub Half", "_Test T1", "_Test FORM 2", weight=50)
        self.assertRaises(frappe.ValidationError, self.publish, exam)

    def test_one_notification_per_student(self):
        with patch("smart_school.notifications.send_notification") as send:
            results.notify_published_exam(self.mid)
        students = [c.args[0] for c in send.call_args_list]
        self.assertEqual(sorted(students), sorted([self.s["a"], self.s["b"]]))
        self.assertIn("_T ENGLISH", send.call_args_list[0].args[1])
        self.assertIn("_T MATH", send.call_args_list[0].args[1])

    def test_no_notification_per_result(self):
        with patch("smart_school.notifications.send_notification") as send:
            add_result(self.s["c"], self.mid, "_T MATH", 55)
        send.assert_not_called()
