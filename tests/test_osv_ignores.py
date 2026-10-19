# Copyright 2026 Lusoris
"""osv-scanner.toml ignores against the OpenVEX statements they mirror.

The OpenSSF Scorecard Vulnerabilities check reads osv-scanner.toml beside the Go module.
Every ignore there must match a not_affected statement of security/vex/go.openvex.json
with the same expiry, carry a category whose fixed interval reaches that expiry from the
entry date, and not be expired. A planted entry of each kind must fail the check.
"""

from __future__ import annotations

import copy
import datetime
import json
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OSV_PATH = ROOT / "osv-scanner.toml"
VEX_PATH = ROOT / "security" / "vex" / "go.openvex.json"
# Fixed rectification intervals of the fleet exception categories; A states its own.
CATEGORY_DAYS = {"B": 3, "C": 10, "D": 120}
NOTES_RE = re.compile(
    r"^category: (?P<category>[A-Z]); entered: (?P<entered>\d{4}-\d{2}-\d{2}); "
    r"expires: (?P<expires>\d{4}-\d{2}-\d{2})$"
)


def vex_expiries(vex: dict) -> dict[str, tuple[str, datetime.date, datetime.date]]:
    """Map each not_affected vulnerability with notes to (category, entered, expires)."""
    found = {}
    for statement in vex["statements"]:
        if statement.get("status") != "not_affected":
            continue
        match = NOTES_RE.match(statement.get("status_notes", ""))
        if match is None:
            continue
        found[statement["vulnerability"]["name"]] = (
            match["category"],
            datetime.date.fromisoformat(match["entered"]),
            datetime.date.fromisoformat(match["expires"]),
        )
    return found


def check_ignore(entry: dict, expiries: dict, today: datetime.date) -> list[str]:
    """Return the defects of one IgnoredVulns entry."""
    vuln = entry.get("id", "")
    if vuln not in expiries:
        return [f"{vuln}: no not_affected VEX statement with category and expiry"]
    category, entered, expires = expiries[vuln]
    defects = []
    if entry.get("ignoreUntil") != expires:
        defects.append(f"{vuln}: ignoreUntil differs from VEX expiry {expires}")
    if category not in CATEGORY_DAYS:
        defects.append(f"{vuln}: category {category} has no fixed interval")
    elif (expires - entered).days > CATEGORY_DAYS[category]:
        defects.append(f"{vuln}: expiry beyond category {category} interval")
    if expires < today:
        defects.append(f"{vuln}: expired on {expires}")
    if f"Category {category}" not in entry.get("reason", ""):
        defects.append(f"{vuln}: reason does not name category {category}")
    return defects


def check_all(osv: dict, vex: dict, today: datetime.date) -> list[str]:
    """Return every defect between osv-scanner.toml and the VEX document."""
    expiries = vex_expiries(vex)
    entries = osv.get("IgnoredVulns", [])
    defects = [d for entry in entries for d in check_ignore(entry, expiries, today)]
    ignored = {entry.get("id") for entry in entries}
    defects.extend(f"{vuln}: VEX statement without osv ignore" for vuln in expiries if vuln not in ignored)
    return defects


@pytest.fixture(scope="module")
def osv() -> dict:
    with OSV_PATH.open("rb") as handle:
        return tomllib.load(handle)


@pytest.fixture(scope="module")
def vex() -> dict:
    return json.loads(VEX_PATH.read_text(encoding="utf-8"))


def test_osv_ignores_match_vex(osv: dict, vex: dict) -> None:
    assert osv["IgnoredVulns"], "osv-scanner.toml lists no ignore"
    assert check_all(osv, vex, datetime.date.today()) == []


def plant_expired(osv: dict, vex: dict) -> None:
    vex["statements"][0]["status_notes"] = "category: D; entered: 2026-01-01; expires: 2026-02-01"
    osv["IgnoredVulns"][0]["ignoreUntil"] = datetime.date(2026, 2, 1)


def plant_long_interval(osv: dict, vex: dict) -> None:
    vex["statements"][0]["status_notes"] = "category: D; entered: 2026-10-19; expires: 2027-03-01"
    osv["IgnoredVulns"][0]["ignoreUntil"] = datetime.date(2027, 3, 1)


def plant_expiry_drift(osv: dict, vex: dict) -> None:
    osv["IgnoredVulns"][0]["ignoreUntil"] = datetime.date(2027, 2, 14)


def plant_unknown_id(osv: dict, vex: dict) -> None:
    osv["IgnoredVulns"].append(dict(osv["IgnoredVulns"][0], id="GO-2099-0001"))


def plant_missing_ignore(osv: dict, vex: dict) -> None:
    osv["IgnoredVulns"].clear()


def plant_category_a(osv: dict, vex: dict) -> None:
    notes = vex["statements"][0]["status_notes"]
    vex["statements"][0]["status_notes"] = notes.replace("category: D", "category: A")


def plant_reason_without_category(osv: dict, vex: dict) -> None:
    osv["IgnoredVulns"][0]["reason"] = "not reachable"


@pytest.mark.parametrize(
    "plant",
    [
        plant_expired,
        plant_long_interval,
        plant_expiry_drift,
        plant_unknown_id,
        plant_missing_ignore,
        plant_category_a,
        plant_reason_without_category,
    ],
)
def test_planted_defects_fail(osv: dict, vex: dict, plant) -> None:
    planted_osv, planted_vex = copy.deepcopy(osv), copy.deepcopy(vex)
    plant(planted_osv, planted_vex)
    assert check_all(planted_osv, planted_vex, datetime.date(2026, 10, 19))
