"""Testes unitários para fire_callback() — escritos antes da implementação (TDD)."""
import pytest
from unittest.mock import MagicMock, patch, call


class TestFireCallbackBasic:
    def test_posts_to_callback_url(self):
        from transcritor.workers.tasks import fire_callback

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

            fire_callback("https://crm.example.com/webhook", {"job_id": "j1", "status": "done"})

        mock_client.post.assert_called_once()
        call_url = mock_client.post.call_args[0][0]
        assert call_url == "https://crm.example.com/webhook"

    def test_sends_payload_as_json(self):
        from transcritor.workers.tasks import fire_callback

        payload = {"job_id": "j1", "status": "done", "text": "hello"}

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = MagicMock(raise_for_status=MagicMock())

            fire_callback("https://example.com/hook", payload)

        _, kwargs = mock_client.post.call_args
        assert kwargs["json"] == payload

    def test_includes_secret_header_when_provided(self):
        from transcritor.workers.tasks import fire_callback

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = MagicMock(raise_for_status=MagicMock())

            fire_callback("https://example.com/hook", {}, secret="my-secret")

        _, kwargs = mock_client.post.call_args
        assert kwargs["headers"].get("X-Callback-Secret") == "my-secret"

    def test_no_secret_header_when_secret_is_none(self):
        from transcritor.workers.tasks import fire_callback

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = MagicMock(raise_for_status=MagicMock())

            fire_callback("https://example.com/hook", {}, secret=None)

        _, kwargs = mock_client.post.call_args
        assert "X-Callback-Secret" not in kwargs["headers"]

    def test_no_secret_header_when_secret_is_empty_string(self):
        from transcritor.workers.tasks import fire_callback

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = MagicMock(raise_for_status=MagicMock())

            fire_callback("https://example.com/hook", {}, secret="")

        _, kwargs = mock_client.post.call_args
        assert "X-Callback-Secret" not in kwargs["headers"]

    def test_uses_timeout(self):
        from transcritor.workers.tasks import fire_callback

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = MagicMock(raise_for_status=MagicMock())

            fire_callback("https://example.com/hook", {})

        _, kwargs = mock_client.post.call_args
        assert "timeout" in kwargs
        assert kwargs["timeout"] > 0

    def test_single_attempt_on_success(self):
        from transcritor.workers.tasks import fire_callback

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = MagicMock(raise_for_status=MagicMock())

            fire_callback("https://example.com/hook", {})

        assert mock_client.post.call_count == 1


class TestFireCallbackRetry:
    def test_retries_on_http_error(self):
        from transcritor.workers.tasks import fire_callback
        import httpx

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            # falha nas duas primeiras, sucesso na terceira
            mock_response_fail = MagicMock()
            mock_response_fail.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock()
            )
            mock_response_ok = MagicMock()
            mock_response_ok.raise_for_status = MagicMock()
            mock_client.post.side_effect = [mock_response_fail, mock_response_fail, mock_response_ok]

            with patch("time.sleep"):
                fire_callback("https://example.com/hook", {})

        assert mock_client.post.call_count == 3

    def test_retries_on_connection_error(self):
        from transcritor.workers.tasks import fire_callback
        import httpx

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_response_ok = MagicMock(raise_for_status=MagicMock())
            mock_client.post.side_effect = [
                httpx.ConnectError("connection refused"),
                mock_response_ok,
            ]

            with patch("time.sleep"):
                fire_callback("https://example.com/hook", {})

        assert mock_client.post.call_count == 2

    def test_sleeps_between_retries(self):
        from transcritor.workers.tasks import fire_callback
        import httpx

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_response_ok = MagicMock(raise_for_status=MagicMock())
            mock_client.post.side_effect = [
                httpx.ConnectError("refused"),
                mock_response_ok,
            ]

            with patch("time.sleep") as mock_sleep:
                fire_callback("https://example.com/hook", {})

        mock_sleep.assert_called_once()

    def test_gives_up_after_max_retries(self):
        from transcritor.workers.tasks import fire_callback
        import httpx

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.side_effect = httpx.ConnectError("always fails")

            with patch("time.sleep"):
                fire_callback("https://example.com/hook", {})

        assert mock_client.post.call_count == 3

    def test_does_not_raise_after_all_retries_exhausted(self):
        """fire_callback nunca deve levantar exceção — falhas são logadas e engolidas."""
        from transcritor.workers.tasks import fire_callback
        import httpx

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.side_effect = httpx.ConnectError("always fails")

            with patch("time.sleep"):
                # não deve levantar
                fire_callback("https://example.com/hook", {"job_id": "j1"})

    def test_no_sleep_after_last_attempt(self):
        """Não deve fazer sleep após a última tentativa fracassada."""
        from transcritor.workers.tasks import fire_callback
        import httpx

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.side_effect = httpx.ConnectError("fails")

            with patch("time.sleep") as mock_sleep:
                fire_callback("https://example.com/hook", {})

        # 3 tentativas → sleep apenas entre elas: 2 vezes (após 1ª e 2ª)
        assert mock_sleep.call_count == 2
