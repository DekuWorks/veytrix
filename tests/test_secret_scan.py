from pathlib import Path

from scan_secrets import scan_repository, scan_text

ROOT = Path(__file__).resolve().parents[1]


def test_local_placeholder_is_not_a_secret() -> None:
    text = "postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5432/veytrix"

    assert scan_text("docker-compose.yml", text) == []
    assert scan_text(".env.example", "POSTGRES_PASSWORD=local-dev-only") == []


def test_real_secret_patterns_fail() -> None:
    aws_key = "AKIA" + "IOSFODNN7EXAMPLE"
    private_key = "-----BEGIN " + "RSA PRIVATE KEY-----"
    database = "postgresql://veytrix:" + "correct-horse-battery" + "@db.internal/veytrix"
    assignment = "api_key=" + "this-is-a-real-token"

    assert any(item.rule == "aws_access_key" for item in scan_text("leak.txt", f"key={aws_key}"))
    assert any(item.rule == "private_key" for item in scan_text("leak.pem", private_key))
    assert any(item.rule == "url_password" for item in scan_text("prod.env", database))
    assert any(item.rule == "assigned_secret" for item in scan_text("prod.env", assignment))


def test_foundry_vendor_dirs_are_skipped_but_other_contract_files_are_not(tmp_path: Path) -> None:
    assignment = "api_key=" + "this-is-a-real-token"
    for folder in ("lib", "out", "cache"):
        vendored = tmp_path / "contracts" / folder / "dep" / "fixture.js"
        vendored.parent.mkdir(parents=True)
        vendored.write_text(assignment)
    (tmp_path / "contracts" / "script").mkdir()
    (tmp_path / "contracts" / "script" / "leak.env").write_text(assignment)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "leak.env").write_text(assignment)

    paths = sorted(item.path for item in scan_repository(tmp_path))

    assert paths == ["contracts/script/leak.env", "lib/leak.env"]


def test_repository_tree_is_clean() -> None:
    assert scan_repository(ROOT) == []
