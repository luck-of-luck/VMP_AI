"""Pure validation helpers behind db_read_vector_search and friends."""

import math

import pytest

from mcp_database.errors import QueryValidationError
from mcp_database.helpers import vector


def test_ensure_vector_happy():
    assert vector.ensure_vector([1, 2.5, -3]) == [1.0, 2.5, -3.0]


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        "1,2,3",
        {"x": 1},
        [1, "2"],
        [1, None],
        [True, False],
        [1, math.nan],
        [1, math.inf],
        [1, -math.inf],
    ],
)
def test_ensure_vector_sad(value):
    with pytest.raises(QueryValidationError):
        vector.ensure_vector(value)


def test_ensure_vector_absurd_dimension_count():
    with pytest.raises(QueryValidationError, match="max 16000"):
        vector.ensure_vector([0.0] * 20_000)


@pytest.mark.parametrize("metric", sorted(vector.METRICS))
def test_ensure_metric_happy(metric):
    assert vector.ensure_metric(metric) == metric


@pytest.mark.parametrize("metric", ["banana", "COSINE", "", "l2 ", "🍌"])
def test_ensure_metric_sad(metric):
    with pytest.raises(QueryValidationError, match="Unknown metric"):
        vector.ensure_metric(metric)


def test_clamp_candidates_defaults_to_ten_times_limit():
    assert vector.clamp_candidates(None, 50) == 500


def test_clamp_candidates_enforces_floor_and_ceiling():
    assert vector.clamp_candidates(None, 5) == 100
    assert vector.clamp_candidates(3, 10) == 100
    assert vector.clamp_candidates(999_999, 10) == 10_000


@pytest.mark.parametrize("value", [0, -1, 1.5, "100", True])
def test_clamp_candidates_sad(value):
    with pytest.raises(QueryValidationError, match="num_candidates"):
        vector.clamp_candidates(value, 10)


def test_ensure_scalar_filter_happy():
    assert vector.ensure_scalar_filter(None) is None
    assert vector.ensure_scalar_filter({"status": "active", "n": 3}) == {"status": "active", "n": 3}


@pytest.mark.parametrize(
    "flt",
    [
        "status=active",
        [("status", "active")],
        {"": "x"},
        {42: "x"},
        {"tags": ["a", "b"]},
        {"meta": {"$gt": 1}},
    ],
)
def test_ensure_scalar_filter_sad(flt):
    with pytest.raises(QueryValidationError):
        vector.ensure_scalar_filter(flt)
