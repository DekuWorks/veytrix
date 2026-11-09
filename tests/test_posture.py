import pytest

from veytrix_api.main import create_app
from veytrix_api.settings import DEFAULT_DATABASE_URL, BootRefused, Settings, get_settings


def test_live_broker_flag_refuses_to_boot() -> None:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=True,
        database_url=DEFAULT_DATABASE_URL,
    )

    with pytest.raises(BootRefused, match="Live broker"):
        create_app(settings)


def test_non_local_environment_refuses_without_an_auth_gateway() -> None:
    settings = Settings(
        veytrix_env="production",
        veytrix_enable_live_broker=False,
        database_url=DEFAULT_DATABASE_URL,
    )

    with pytest.raises(BootRefused, match="auth gateway"):
        create_app(settings)


def test_remote_database_host_refuses_to_boot() -> None:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url="postgresql+psycopg://veytrix:local-dev-only@db.example.com:5432/veytrix",
    )

    with pytest.raises(BootRefused, match="DATABASE_URL"):
        create_app(settings)


def test_invalid_live_broker_value_refuses_to_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VEYTRIX_ENABLE_LIVE_BROKER", "maybe")
    get_settings.cache_clear()
    try:
        with pytest.raises(BootRefused):
            create_app()
    finally:
        get_settings.cache_clear()


def test_local_paper_configuration_boots() -> None:
    app = create_app(
        Settings(
            veytrix_env="local",
            veytrix_enable_live_broker=False,
            database_url=DEFAULT_DATABASE_URL,
        )
    )

    assert app.state.settings.veytrix_env == "local"
    assert app.state.settings.veytrix_enable_live_broker is False
