"""CLI tests."""

import subprocess
import sys


def test_cli_version():
    r = subprocess.run(
        [sys.executable, "-m", "counter", "--version"], capture_output=True, text=True
    )
    assert r.returncode == 0
    assert "1.0.0" in r.stdout


def test_cli_help():
    r = subprocess.run(
        [sys.executable, "-m", "counter", "--help"], capture_output=True, text=True
    )
    assert r.returncode == 0
    assert "stl" in r.stdout
    assert "animate" in r.stdout
