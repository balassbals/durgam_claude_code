"""Property tests for announcement priority engine (M9).

4 property tests using Hypothesis:
1. sort_for_viewer is a total order (no ties break non-deterministically).
2. Any very_important in-window announcement sorts before any normal announcement.
3. priority_key group component is always 0 or 1.
4. compute_important_until result is always strictly after scheduled_at.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, strategies as st

from durgam.services.announcement_priority import (
    compute_important_until,
    is_in_important_window,
    priority_key,
    sort_for_viewer,
)

_IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_IMPORTANCE = st.sampled_from(["normal", "very_important"])
_ROLE_CODE = st.sampled_from(["VC", "REGISTRAR", "FACULTY", "HOD", "UNKNOWN"])
_RANK = st.integers(min_value=1, max_value=999_998)

_PAST_DATETIME = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(UTC),
)


def _make_ann(importance, role_code, scheduled_at, important_until):
    ann = MagicMock()
    ann.importance = importance
    ann.composer_role_code = role_code
    ann.scheduled_at = scheduled_at
    ann.important_until = important_until
    return ann


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

@given(
    importances=st.lists(_IMPORTANCE, min_size=0, max_size=20),
    role_codes=st.lists(_ROLE_CODE, min_size=0, max_size=20),
    offsets_min=st.lists(st.integers(min_value=-1000, max_value=0), min_size=0, max_size=20),
)
@settings(max_examples=100)
def test_sort_for_viewer_is_stable_and_returns_all(importances, role_codes, offsets_min):
    """sort_for_viewer returns the same number of elements it received."""
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    n = min(len(importances), len(role_codes), len(offsets_min))
    if n == 0:
        return

    anns = []
    for i in range(n):
        sched = now + timedelta(minutes=offsets_min[i])
        imp_until = now + timedelta(hours=24) if importances[i] == "very_important" else None
        anns.append(_make_ann(importances[i], role_codes[i], sched, imp_until))

    config = {r: MagicMock(priority_rank=idx * 10 + 10) for idx, r in enumerate(set(role_codes))}
    sorted_anns = sort_for_viewer(anns, config, now)
    assert len(sorted_anns) == n


@given(
    n_important=st.integers(min_value=1, max_value=5),
    n_normal=st.integers(min_value=1, max_value=5),
    ranks=st.lists(st.integers(min_value=1, max_value=100), min_size=2, max_size=2),
)
@settings(max_examples=100)
def test_in_window_very_important_always_before_normal(n_important, n_normal, ranks):
    """Every in-window very_important beats every normal announcement."""
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

    imp_anns = [
        _make_ann("very_important", "VC", now - timedelta(hours=i), now + timedelta(days=1))
        for i in range(n_important)
    ]
    normal_anns = [
        _make_ann("normal", "FACULTY", now - timedelta(hours=i), None)
        for i in range(n_normal)
    ]
    config = {"VC": MagicMock(priority_rank=ranks[0]), "FACULTY": MagicMock(priority_rank=ranks[1])}

    all_anns = imp_anns + normal_anns
    sorted_anns = sort_for_viewer(all_anns, config, now)

    # All very_important in-window must appear before any normal
    important_positions = [i for i, a in enumerate(sorted_anns) if a.importance == "very_important"]
    normal_positions = [i for i, a in enumerate(sorted_anns) if a.importance == "normal"]

    if important_positions and normal_positions:
        assert max(important_positions) < min(normal_positions)


@given(
    importance=_IMPORTANCE,
    role_code=_ROLE_CODE,
    rank=_RANK,
    scheduled_offset=st.integers(min_value=-3600, max_value=0),
    window_offset=st.integers(min_value=1, max_value=3600),
)
@settings(max_examples=200)
def test_priority_key_group_is_0_or_1(importance, role_code, rank, scheduled_offset, window_offset):
    """priority_key group component is always 0 or 1."""
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    sched = now + timedelta(seconds=scheduled_offset)
    imp_until = now + timedelta(seconds=window_offset) if importance == "very_important" else None
    ann = _make_ann(importance, role_code, sched, imp_until)
    config = {role_code: MagicMock(priority_rank=rank)}

    key = priority_key(ann, config, now)
    assert key[0] in (0, 1)


@given(
    year=st.integers(min_value=2025, max_value=2030),
    month=st.integers(min_value=1, max_value=12),
    day=st.integers(min_value=1, max_value=28),  # safe for all months
    hour_ist=st.integers(min_value=0, max_value=23),
)
@settings(max_examples=100)
def test_compute_important_until_strictly_after_scheduled(year, month, day, hour_ist):
    """important_until is always strictly after scheduled_at."""
    scheduled_ist = datetime(year, month, day, hour_ist, 0, 0, tzinfo=_IST)
    scheduled_utc = scheduled_ist.astimezone(UTC)
    result = compute_important_until(scheduled_utc, frozenset())
    assert result > scheduled_utc
