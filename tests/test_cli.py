"""CLI smoke tests - offline (explicit args, no live fetch, no trades)."""
from __future__ import annotations

import pytest

from ballast.portfolio.__main__ import main


def test_setup_offline(capsys):
    rc = main(["setup", "--total", "300000", "--price", "198"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "1,325" in out
    assert "87.45%" in out


def test_check_hold(capsys):
    rc = main(["check", "--lot", "1325", "--price", "198", "--cash", "37500"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "HOLD" in out


def test_check_sell_signal(capsys):
    rc = main(["check", "--lot", "1600", "--price", "198", "--cash", "10000"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "SAT" in out


def test_check_buy_signal(capsys):
    rc = main(["check", "--lot", "1000", "--price", "198", "--cash", "120000"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "AL" in out


def test_no_command_errors():
    with pytest.raises(SystemExit):
        main([])
