import pytest


@pytest.fixture()
def reset_engine():
    """Reseta o singleton do WhisperEngine entre testes."""
    import transcritor.engine.registry as registry
    registry._engine = None
    yield
    registry._engine = None


@pytest.fixture()
def reset_settings():
    """Limpa o cache do lru_cache de get_settings entre testes."""
    from transcritor.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
