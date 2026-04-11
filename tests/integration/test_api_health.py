"""
Testes dos endpoints de health check.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch


@pytest.fixture
async def client():
    from transcritor.api.app import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestHealth:
    async def test_health_returns_200(self, client):
        r = await client.get("/health")
        assert r.status_code == 200

    async def test_health_response_has_status_ok(self, client):
        r = await client.get("/health")
        assert r.json()["status"] == "ok"


class TestReady:
    async def test_ready_returns_200_when_redis_available(self, client):
        with patch("transcritor.api.routers.health.redis") as mock_redis:
            mock_redis.from_url.return_value.ping.return_value = True
            r = await client.get("/ready")
        assert r.status_code == 200

    async def test_ready_response_has_redis_ok(self, client):
        with patch("transcritor.api.routers.health.redis") as mock_redis:
            mock_redis.from_url.return_value.ping.return_value = True
            r = await client.get("/ready")
        assert r.json()["redis"] == "ok"

    async def test_ready_returns_503_when_redis_unavailable(self, client):
        with patch("transcritor.api.routers.health.redis") as mock_redis:
            mock_redis.from_url.return_value.ping.side_effect = Exception("refused")
            r = await client.get("/ready")
        assert r.status_code == 503
