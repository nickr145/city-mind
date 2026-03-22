"""
Tests for backend/privacy.py — apply_privacy() function.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from privacy import apply_privacy, SUPPRESSION_THRESHOLD, PII_FIELDS, STRIP_ALWAYS


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_planning_rows(n=10):
    return [
        {
            "permit_no": f"24-{i:06d}",
            "permit_type": "Residential Building (House)",
            "permit_status": "Issued",
            "work_type": "New Construction",
            "construction_value": 250000.0 + i * 1000,
            "issue_date": "2024-06-01",
            "owners": f"Owner {i}",
            "applicant": f"Applicant {i}",
            "contractor": f"Contractor {i}",
            "contractor_contact": "555-0100",
            "roll_no": f"ROLL{i}",
            "legal_description": "LOT 1 PLAN 1234",
            "parcel_id": f"PARCEL{i}",
            "folder_rsn": f"RSN{i}",
            "source_id": "kitchener",
            "synced_at": "2026-03-22T00:00:00",
        }
        for i in range(n)
    ]


PRESSURE_ZONES = ["KIT 1", "KIT 2E", "KIT 4", "BRIDGEPORT", "CAM 1", "CAM 2W"]


def make_engineering_rows(n=10):
    return [
        {
            "watmain_id": f"WM{i:04d}",
            "status": "ACTIVE",
            "pressure_zone": PRESSURE_ZONES[i % len(PRESSURE_ZONES)],
            "pipe_size": 150.0 + i * 10,
            "material": "PVC",
            "criticality": float(i % 5 + 1),
            "source_id": "kitchener",
            "synced_at": "2026-03-22T00:00:00",
        }
        for i in range(n)
    ]


def make_transit_rows(n=10):
    return [
        {
            "stop_id": f"STOP{i:04d}",
            "street": "King St",
            "crossstreet": f"Ave {i}",
            "municipality": ["Kitchener", "Waterloo", "Cambridge"][i % 3],
            "ixpress": "Y" if i % 3 == 0 else "N",
            "status": "Active",
            "source_id": "kitchener",
            "synced_at": "2026-03-22T00:00:00",
        }
        for i in range(n)
    ]


# ── Access level: none ────────────────────────────────────────────────────────

def test_no_access_returns_empty():
    rows = make_planning_rows(10)
    result = apply_privacy(rows, "planning", "unknown_role")
    assert result["access_level"] == "none"
    assert result["rows"] == []
    assert "note" in result


def test_unknown_dept_returns_none():
    result = apply_privacy([{"x": 1}], "health", "admin")
    assert result["access_level"] == "none"


# ── STRIP_ALWAYS ──────────────────────────────────────────────────────────────

def test_strip_always_removed_for_full_access():
    rows = make_engineering_rows(5)
    result = apply_privacy(rows, "engineering", "admin")
    assert result["access_level"] == "full"
    for row in result["rows"]:
        for field in STRIP_ALWAYS:
            assert field not in row, f"{field} should be stripped"


def test_strip_always_removed_for_read_access():
    rows = make_planning_rows(5)
    result = apply_privacy(rows, "planning", "engineer")
    assert result["access_level"] == "read"
    for row in result["rows"]:
        for field in STRIP_ALWAYS:
            assert field not in row


# ── Full access ───────────────────────────────────────────────────────────────

def test_full_access_preserves_all_non_stripped_fields():
    rows = make_engineering_rows(5)
    result = apply_privacy(rows, "engineering", "admin")
    assert result["access_level"] == "full"
    assert len(result["rows"]) == 5
    for row in result["rows"]:
        assert "watmain_id" in row
        assert "pressure_zone" in row


def test_full_access_planning_preserves_pii():
    rows = make_planning_rows(5)
    result = apply_privacy(rows, "planning", "admin")
    assert result["access_level"] == "full"
    for row in result["rows"]:
        assert "owners" in row
        assert "applicant" in row


# ── Read access ───────────────────────────────────────────────────────────────

def test_read_access_strips_pii():
    rows = make_planning_rows(10)
    result = apply_privacy(rows, "planning", "engineer")
    assert result["access_level"] == "read"
    pii = PII_FIELDS["planning"]
    for row in result["rows"]:
        for field in pii:
            assert field not in row, f"PII field '{field}' should be stripped"
        assert "permit_no" in row


def test_read_access_transit_no_pii_to_strip():
    rows = make_transit_rows(10)
    result = apply_privacy(rows, "transit", "analyst")
    assert result["access_level"] == "read"
    assert len(result["rows"]) == 10
    for row in result["rows"]:
        assert "stop_id" in row


# ── Aggregated access ─────────────────────────────────────────────────────────

def test_aggregated_groups_by_pressure_zone():
    rows = make_engineering_rows(30)
    result = apply_privacy(rows, "engineering", "planner")
    assert result["access_level"] == "aggregated"
    for group in result["rows"]:
        assert "pressure_zone" in group
        assert "record_count" in group
        assert "avg_pipe_size" in group
        assert "avg_criticality" in group


def test_aggregated_computes_record_counts():
    rows = make_engineering_rows(30)
    result = apply_privacy(rows, "engineering", "planner")
    total = sum(g["record_count"] for g in result["rows"])
    assert total == 30


def test_aggregated_suppressed_when_too_few_groups():
    # Only 1 group (all same pressure_zone)
    rows = [
        {"watmain_id": f"WM{i}", "pressure_zone": "KIT 1", "pipe_size": 100.0,
         "criticality": 3.0, "source_id": "k", "synced_at": "2026-01-01"}
        for i in range(10)
    ]
    result = apply_privacy(rows, "engineering", "planner")
    assert result["access_level"] == "suppressed"
    assert result["rows"] == []
    assert "note" in result


# ── Anonymized access ─────────────────────────────────────────────────────────

def test_anonymized_strips_pii():
    rows = make_planning_rows(20)
    result = apply_privacy(rows, "engineering", "analyst")
    # engineering has no PII, but access should be anonymized
    assert result["access_level"] == "anonymized"


def test_anonymized_suppressed_when_fewer_than_threshold():
    rows = make_engineering_rows(SUPPRESSION_THRESHOLD - 1)
    result = apply_privacy(rows, "engineering", "analyst")
    assert result["access_level"] == "suppressed"
    assert result["rows"] == []
    assert "note" in result


def test_anonymized_not_suppressed_at_threshold():
    rows = make_engineering_rows(SUPPRESSION_THRESHOLD)
    result = apply_privacy(rows, "engineering", "analyst")
    assert result["access_level"] == "anonymized"
    assert len(result["rows"]) == SUPPRESSION_THRESHOLD


# ── Suppression threshold ─────────────────────────────────────────────────────

def test_suppression_threshold_value():
    assert SUPPRESSION_THRESHOLD == 5


def test_suppression_returns_note():
    rows = make_engineering_rows(2)
    result = apply_privacy(rows, "engineering", "analyst")
    assert result["access_level"] == "suppressed"
    assert "suppressed" in result["note"].lower()
    assert str(SUPPRESSION_THRESHOLD) in result["note"]
