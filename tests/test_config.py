import os
import subprocess
import sys
from pathlib import Path

import pytest

from config import require_app_password


@pytest.mark.parametrize("password", [None, "", " \t\n"])
def test_require_app_password_rejects_missing_or_blank_values(monkeypatch, password):
    if password is None:
        monkeypatch.delenv("APP_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("APP_PASSWORD", password)

    with pytest.raises(RuntimeError, match="APP_PASSWORD must be set and not blank"):
        require_app_password()


def test_require_app_password_preserves_password_exactly(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", " password-with-spaces ")
    assert require_app_password() == " password-with-spaces "


@pytest.mark.parametrize("module", ["main", "database_setup"])
@pytest.mark.parametrize("password", [None, "", " \t\n", "test-startup-password"])
def test_startup_requires_password_before_creating_database(tmp_path, module, password):
    env = os.environ.copy()
    env.pop("APP_PASSWORD", None)
    if password is not None:
        env["APP_PASSWORD"] = password
    database_path = tmp_path / "startup.db"
    env["DB_PATH"] = str(database_path)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    # An actual local .env must not mask a missing deployment setting in this test.
    env["PYTHON_DOTENV_DISABLED"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if password and password.strip():
        assert result.returncode == 0, result.stderr
        assert database_path.exists()
    else:
        assert result.returncode != 0
        assert "APP_PASSWORD must be set and not blank" in result.stderr
        assert not database_path.exists()
