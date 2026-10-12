# Copyright 2026 Lusoris
"""Skip or fail a test whose host prerequisite is missing.

Tests that need Docker, bash, or a preparation step bounded in time skip on a host
that lacks the prerequisite, so the local gate stays usable on a loaded workstation.
CI sets IMAGO_REQUIRE_LIVE_TESTS=1; there the same condition fails the test, so a live
test that did not run cannot report green.
"""

from collections.abc import Mapping
from typing import NoReturn

import pytest

REQUIRE_LIVE_ENV = "IMAGO_REQUIRE_LIVE_TESTS"


def live_tests_required(environ: Mapping[str, str]) -> bool:
    """True only when the variable is exactly "1"; any other value keeps the skip."""
    return environ.get(REQUIRE_LIVE_ENV) == "1"


def skip_or_fail(reason: str, environ: Mapping[str, str]) -> NoReturn:
    """Skip with `reason`, or fail with it when live tests are required."""
    if live_tests_required(environ):
        pytest.fail(f"{reason}; {REQUIRE_LIVE_ENV}=1 requires this test to run", pytrace=False)
    pytest.skip(reason)
