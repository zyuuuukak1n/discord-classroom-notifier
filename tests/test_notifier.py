"""Tests for NotifierService orchestration and dispatch logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.classroom import ClassroomItem
from src.config import AppConfig, CourseConfig
from src.notifier import NotifierService


class TestNotifierService:
    """Test notification workflow and deduplication integration."""

    @patch("src.notifier.get_credentials")
    @patch("src.notifier.ClassroomClient")
    def test_run_once_initial_sync_marks_as_read(
        self, mock_classroom_cls, mock_get_creds, tmp_path: Path
    ):
        data_dir = tmp_path / "data"
        config = AppConfig(
            discord_default_webhook_url="https://discord.com/api/webhooks/123/token",
            data_dir=str(data_dir),
            initial_sync_mark_as_read=True,
            courses=[CourseConfig(course_id="c1", course_name="Course 1")],
        )

        mock_classroom = MagicMock()
        mock_classroom_cls.return_value = mock_classroom
        mock_classroom.verify_course_access.return_value = True

        dummy_item = ClassroomItem(
            item_id="item_1",
            course_id="c1",
            course_name="Course 1",
            item_type="announcement",
            title="Old Post",
            text="Initial post",
            update_time="2026-10-01T00:00:00Z",
            creation_time="2026-10-01T00:00:00Z",
        )
        mock_classroom.fetch_recent_announcements.return_value = [dummy_item]
        mock_classroom.fetch_recent_coursework.return_value = []
        mock_classroom.fetch_recent_materials.return_value = []

        service = NotifierService(config)

        # 初回同期時は通知を送信せず既読化のみ行う
        with patch.object(service.discord_client, "send_notification") as mock_send:
            sent = service.run_once()
            assert sent == 0
            mock_send.assert_not_called()

        assert service.storage.is_course_initialized("c1") is True
        assert service.storage.is_item_notified(dummy_item) is True

    @patch("src.notifier.get_credentials")
    @patch("src.notifier.ClassroomClient")
    def test_run_once_subsequent_run_dispatches_notification(
        self, mock_classroom_cls, mock_get_creds, tmp_path: Path
    ):
        data_dir = tmp_path / "data"
        config = AppConfig(
            discord_default_webhook_url="https://discord.com/api/webhooks/123/token",
            data_dir=str(data_dir),
            initial_sync_mark_as_read=True,
            courses=[CourseConfig(course_id="c1", course_name="Course 1")],
        )

        service = NotifierService(config)
        service.storage.mark_course_initialized("c1")

        mock_classroom = MagicMock()
        mock_classroom_cls.return_value = mock_classroom
        mock_classroom.verify_course_access.return_value = True

        new_item = ClassroomItem(
            item_id="item_new",
            course_id="c1",
            course_name="Course 1",
            item_type="announcement",
            title="New Post",
            text="New announcement content",
            update_time="2026-10-02T10:00:00Z",
            creation_time="2026-10-02T10:00:00Z",
        )
        mock_classroom.fetch_recent_announcements.return_value = [new_item]
        mock_classroom.fetch_recent_coursework.return_value = []
        mock_classroom.fetch_recent_materials.return_value = []

        with patch.object(
            service.discord_client, "send_notification", return_value=True
        ) as mock_send:
            sent = service.run_once()
            assert sent == 1
            mock_send.assert_called_once()

        assert service.storage.is_item_notified(new_item) is True
