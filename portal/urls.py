from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("register/student/", views.student_register, name="register_student"),
    path("register/teacher/", views.teacher_register, name="register_teacher"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("go/", views.role_redirect, name="role_redirect"),
    path("teacher-dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("student-dashboard/", views.student_dashboard, name="student_dashboard"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-dashboard/user/<int:user_id>/toggle/", views.admin_toggle_user, name="admin_toggle_user"),
    path("admin-dashboard/course/<int:course_id>/delete/", views.admin_delete_course, name="admin_delete_course"),
    path("admin-dashboard/platform-settings/", views.admin_update_platform_settings, name="admin_update_platform_settings"),
    path("teacher/course/add/", views.teacher_course_add, name="teacher_course_add"),
    path("teacher/course/<int:course_id>/edit/", views.teacher_course_edit, name="teacher_course_edit"),
    path("teacher/course/<int:course_id>/lessons/", views.teacher_course_lessons, name="teacher_course_lessons"),
    path("teacher/course/<int:course_id>/lessons/add/", views.teacher_course_lesson_add, name="teacher_course_lesson_add"),
    path("teacher/course/<int:course_id>/lessons/<int:lesson_id>/edit/", views.teacher_lesson_edit, name="teacher_lesson_edit"),
    path(
        "teacher/course/<int:course_id>/test/add/",
        views.teacher_course_test_add,
        name="teacher_course_test_add",
    ),
    path("teacher/profile/", views.teacher_profile, name="teacher_profile"),
    path("teacher/profile/edit/", views.teacher_profile_edit, name="teacher_profile_edit"),
    path("student/profile/edit/", views.student_profile_edit, name="student_profile_edit"),
    path("teacher/lesson/add/", views.teacher_lesson_add, name="teacher_lesson_add"),
    path("courses/", views.student_courses, name="student_courses"),
    path("courses/<int:course_id>/", views.student_course_detail, name="student_course_detail"),
    path("courses/<int:course_id>/payment/", views.course_payment, name="course_payment"),
    path("courses/<int:course_id>/payment/success/", views.payment_success, name="payment_success"),
    path("courses/<int:course_id>/enroll/", views.enroll_course, name="enroll_course"),
    path("courses/<int:course_id>/test/", views.student_course_test, name="student_course_test"),
    path(
        "courses/test-result/<int:attempt_id>/",
        views.student_course_test_result,
        name="student_course_test_result",
    ),
    path(
        "courses/test-result/<int:attempt_id>/certificate/",
        views.download_course_certificate,
        name="download_course_certificate",
    ),
    path(
        "courses/<int:course_id>/lesson/<int:lesson_id>/",
        views.student_lesson_detail,
        name="student_lesson_detail",
    ),
    path(
        "courses/<int:course_id>/lesson/<int:lesson_id>/complete/",
        views.complete_lesson,
        name="complete_lesson",
    ),
    path(
        "courses/<int:course_id>/lesson/<int:lesson_id>/comment/",
        views.add_lesson_comment,
        name="add_lesson_comment",
    ),
    path(
        "courses/<int:course_id>/review/<int:review_id>/reply/",
        views.teacher_review_reply,
        name="teacher_review_reply",
    ),
    path("teachers/", views.teachers_list, name="teachers_list"),
    path("teachers/<int:teacher_id>/", views.teacher_public_profile, name="teacher_public_profile"),
]
