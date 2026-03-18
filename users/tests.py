from types import SimpleNamespace

from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from teacher.models import Assignment, ClassRoom, Submission
from users.templatetags.breadcrumbs import module_breadcrumbs
from users.models import User


class BreadcrumbTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.teacher = User.objects.create_user(
            username="teacher1",
            password="pass123",
            role="teacher",
        )
        self.student = User.objects.create_user(
            username="student1",
            password="pass123",
            role="student",
        )
        self.classroom = ClassRoom.objects.create(
            name="Python Batch",
            description="Algorithms",
            teacher=self.teacher,
        )
        self.assignment = Assignment.objects.create(
            classroom=self.classroom,
            title="Arrays Homework",
            description="Solve problems",
            due_date=timezone.now() + timezone.timedelta(days=3),
            assignment_type=Assignment.ASSIGNMENT_TYPE_FILE,
        )
        self.submission = Submission.objects.create(
            assignment=self.assignment,
            student=self.student,
            file="assignments/test.txt",
        )

    def _build_request(self, route_name, kwargs=None):
        request = self.factory.get("/")
        request.resolver_match = SimpleNamespace(url_name=route_name, kwargs=kwargs or {})
        return request

    def test_student_daily_challenge_parent_is_clickable(self):
        items = module_breadcrumbs(
            {"request": self._build_request("daily_challenge_workspace", {"challenge_id": 1})},
            "student",
        )["breadcrumb_items"]

        self.assertEqual(items[1]["label"], "Daily Challenge")
        self.assertEqual(items[1]["url"], reverse("daily_challenges_today"))
        self.assertTrue(items[2]["current"])

    def test_teacher_assignment_parent_is_clickable_on_detail_page(self):
        items = module_breadcrumbs(
            {"request": self._build_request("assignment_detail", {"id": self.assignment.id})},
            "teacher",
        )["breadcrumb_items"]

        self.assertEqual(items[1]["label"], "Assignments")
        self.assertEqual(items[1]["url"], reverse("assignment_list", kwargs={"class_id": self.classroom.id}))

    def test_teacher_assignment_parent_is_clickable_on_grading_page(self):
        items = module_breadcrumbs(
            {"request": self._build_request("grade_file_submission", {"submission_id": self.submission.id})},
            "teacher",
        )["breadcrumb_items"]

        self.assertEqual(items[1]["label"], "Assignments")
        self.assertEqual(items[1]["url"], reverse("assignment_list", kwargs={"class_id": self.classroom.id}))

    def test_teacher_performance_parent_is_clickable_on_student_detail_page(self):
        items = module_breadcrumbs(
            {"request": self._build_request("student_performance", {"class_id": self.classroom.id, "student_id": self.student.id})},
            "teacher",
        )["breadcrumb_items"]

        self.assertEqual(items[1]["label"], "Performance")
        self.assertEqual(items[1]["url"], reverse("performance_list", kwargs={"class_id": self.classroom.id}))

    def test_teacher_daily_challenge_parent_is_clickable(self):
        items = module_breadcrumbs(
            {"request": self._build_request("teacher_submit_question_template")},
            "teacher",
        )["breadcrumb_items"]

        self.assertEqual(items[1]["label"], "Daily Challenge")
        self.assertEqual(items[1]["url"], reverse("teacher_submit_question_template"))
