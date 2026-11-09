"""Fail if the tree contains a high-confidence secret.

The local database password `local-dev-only` is an obvious placeholder and is
allowed. Real key material still fails. This is the scanner CI runs; it does
not replace a hosted secret store.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "postgres-data",
    "venv",
}
# Gitignored Foundry dependencies and build output. Vendored test fixtures hold fake keys.
SKIP_PATHS = {
    ("contracts", "lib"),
    ("contracts", "out"),
    ("contracts", "cache"),
}
SKIP_SUFFIXES = {
    ".eot",
    ".gif",
    ".gz",
    ".ico",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".png",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
}
_PATTERNS = (
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_temporary_key", re.compile(r"ASIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("github_fine_grained_token", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("stripe_live_key", re.compile(r"sk_live_[A-Za-z0-9]{16,}")),
)
_URL_PASSWORD = re.compile(r"\b[a-z][a-z0-9+.-]*://([^/\s:@]+):([^/\s@]+)@", re.IGNORECASE)
_ASSIGNMENT = re.compile(
    r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|private[_-]?key)\b\s*[:=]\s*['\"]?"
    r"([^\s'\"]+)"
)


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}"


def _password_allowed(value: str) -> bool:
    if value == "local-dev-only" or "local-dev-only" in value:
        return True
    return value.startswith("${") and value.endswith("}")


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in _PATTERNS:
            if pattern.search(line):
                findings.append(Finding(rule, path, line_number))
        for match in _URL_PASSWORD.finditer(line):
            if not _password_allowed(match.group(2)):
                findings.append(Finding("url_password", path, line_number))
        for match in _ASSIGNMENT.finditer(line):
            value = match.group(1)
            if _password_allowed(value) or value.startswith("<") or value.startswith("${"):
                continue
            if any(character in value for character in "().[]{}"):
                continue
            if len(value) < 12:
                continue
            findings.append(Finding("assigned_secret", path, line_number))
    return findings


def scan_repository(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in relative):
            continue
        if relative[:2] in SKIP_PATHS:
            continue
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        text = data.decode("utf-8", errors="replace")
        findings.extend(scan_text(str(path.relative_to(root)), text))
    return findings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = scan_repository(root)
    if not findings:
        print("secret scan: no findings")
        return 0
    for finding in findings:
        print(finding)
    print(f"secret scan: {len(findings)} finding(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
