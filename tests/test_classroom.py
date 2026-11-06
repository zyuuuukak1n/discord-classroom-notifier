"""Tests for Google Classroom API client, authorization (IDOR prevention), and retries."""

from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError
from httplib2 import Response

from src.classroom import ClassroomClient


class TestClassroomClient:
    """Test Classroom API calls and security/authorization verification."""

    @patch("src.classroom.build")
    def test_verify_course_access_authorized(self, mock_build):
        # ユーザーが所属しているアクティブコース一覧に該当コースIDが存在する場合
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_courses_resource = mock_service.courses.return_value
        mock_list_req = mock_courses_resource.list.return_value
        mock_list_req.execute.return_value = {
            "courses": [{"id": "course_123", "name": "Valid Course", "courseState": "ACTIVE"}]
        }

        creds = MagicMock()
        client = ClassroomClient(creds)

        # 認可チェック: アクセス可能
        assert client.verify_course_access("course_123") is True

    @patch("src.classroom.build")
    def test_verify_course_access_unauthorized_idor_attempt(self, mock_build):
        """Security Test: Ensure IDOR attempts against courses the user doesn't belong to are blocked."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_courses_resource = mock_service.courses.return_value
        mock_list_req = mock_courses_resource.list.return_value
        # ユーザーの所属コース一覧には course_123 しかない
        mock_list_req.execute.return_value = {
            "courses": [{"id": "course_123", "name": "User's Course", "courseState": "ACTIVE"}]
        }

        # 権限外の course_456 を直接取得しようとすると 403 Forbidden が返る
        resp = Response({"status": 403})
        mock_get_req = mock_courses_resource.get.return_value
        mock_get_req.execute.side_effect = HttpError(resp, b'{"error": "Forbidden"}')

        creds = MagicMock()
        client = ClassroomClient(creds)

        # 権限外コースへのアクセス試行
        assert client.verify_course_access("course_456") is False

    @patch("src.classroom.build")
    def test_fetch_announcements_parsing(self, mock_build):
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # course name get mock
        mock_courses_resource = mock_service.courses.return_value
        mock_get_req = mock_courses_resource.get.return_value
        mock_get_req.execute.return_value = {"id": "c1", "name": "Computer Science"}

        # announcements list mock
        mock_ann_resource = mock_courses_resource.announcements.return_value
        mock_ann_list_req = mock_ann_resource.list.return_value
        mock_ann_list_req.execute.return_value = {
            "announcements": [
                {
                    "id": "ann_101",
                    "text": "Tomorrow class is cancelled.\nPlease read chapter 3.",
                    "alternateLink": "https://classroom.google.com/c/1/m/101",
                    "creationTime": "2026-10-01T08:00:00Z",
                    "updateTime": "2026-10-01T08:05:00Z",
                    "materials": [
                        {
                            "driveFile": {
                                "driveFile": {
                                    "title": "Chapter3.pdf",
                                    "alternateLink": "https://drive.google.com/open?id=xyz",
                                }
                            }
                        }
                    ],
                }
            ]
        }

        creds = MagicMock()
        client = ClassroomClient(creds)
        items = client.fetch_recent_announcements("c1")

        assert len(items) == 1
        item = items[0]
        assert item.item_id == "ann_101"
        assert item.course_name == "Computer Science"
        assert item.title == "Tomorrow class is cancelled."
        assert len(item.attachments) == 1
        assert item.attachments[0].title == "Chapter3.pdf"
        assert item.alternate_link == "https://classroom.google.com/c/1/m/101"

    @patch("time.sleep")
    @patch("src.classroom.build")
    def test_transient_error_retry(self, mock_build, mock_sleep):
        """Test exponential backoff on transient HTTP 500 error."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        resp_500 = Response({"status": 500})
        error_500 = HttpError(resp_500, b"Internal Server Error")

        success_response = {"courses": [{"id": "c1", "name": "Course 1", "courseState": "ACTIVE"}]}

        mock_req = MagicMock()
        mock_req.execute.side_effect = [error_500, success_response]
        mock_service.courses.return_value.list.return_value = mock_req

        creds = MagicMock()
        client = ClassroomClient(creds)
        courses = client.get_enrolled_courses()

        assert len(courses) == 1
        assert mock_req.execute.call_count == 2
        mock_sleep.assert_called_with(1.0)

    def test_format_due_date_jst_conversion(self):
        """Test Classroom UTC due date/time conversion into JST."""
        creds = MagicMock()
        client = ClassroomClient(creds)

        # 1. UTC 14:59 on Oct 15 -> JST 23:59 on Oct 15
        due_date = {"year": 2026, "month": 10, "day": 15}
        due_time = {"hours": 14, "minutes": 59}
        formatted = client._format_due_date(due_date, due_time)
        assert formatted == "2026/10/15 23:59 (JST)"

        # 2. Date only -> 23:59 (JST)
        formatted_date_only = client._format_due_date(due_date, None)
        assert formatted_date_only == "2026/10/15 23:59 (JST)"

        # 3. None due date
        assert client._format_due_date(None, None) is None
