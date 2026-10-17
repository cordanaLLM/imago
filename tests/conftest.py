# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Suite-wide guard: no test may signal process group 1, 0, a negative group or its own.

`os.killpg(1, sig)` is `kill(-1, sig)` and kills every process the user owns, the desktop
session included. A test that hands a mock process to code under test must never reach
that call, so every test runs with `os.killpg` wrapped: a refused id fails the test and the
real call is never made. Ids that name a foreign group pass through unchanged.
"""

from __future__ import annotations

import os

import pytest

_REAL_KILLPG = os.killpg


def _guarded_killpg(pgid: object, sig: int) -> None:
    if not isinstance(pgid, int) or isinstance(pgid, bool) or pgid <= 1 or pgid == os.getpgrp():
        raise AssertionError(f"test tried os.killpg({pgid!r}, {sig}); refused")
    _REAL_KILLPG(pgid, sig)


@pytest.fixture(autouse=True)
def _no_wide_killpg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "killpg", _guarded_killpg)
