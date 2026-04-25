"""Tests for TOOL-02: calculate_route with zone derivation and TTL cache."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.agent.tools import calculate_route as mod
from backend.agent.tools.calculate_route import calculate_route


@pytest.fixture(autouse=True)
def _clear_cache():
    """Reset the module-level cache between tests."""
    mod._route_cache.clear()
    yield
    mod._route_cache.clear()


def _make_client(directions_resp, geocode_resp) -> MagicMock:
    client = MagicMock()
    client.directions.return_value = directions_resp
    client.geocode.return_value = geocode_resp
    return client


def test_directions_parsing_returns_route_data(
    mocker, gmaps_directions_fixture, gmaps_geocode_bangkok_fixture
):
    client = _make_client(gmaps_directions_fixture, gmaps_geocode_bangkok_fixture)
    mocker.patch.object(mod, "_client", return_value=client)

    result = calculate_route("Bangkok", "Nonthaburi")

    assert result.origin == "Bangkok"
    assert result.destination == "Nonthaburi"
    assert result.distance_km == pytest.approx(15.2)
    assert result.duration_min == 30
    # ratio 2400/1800 = 1.333 -> severity 3 (< 1.5 threshold)
    assert result.traffic_severity == 3
    assert result.zone == "central-1"


@pytest.mark.parametrize(
    "ratio,expected",
    [(1.05, 1), (1.2, 2), (1.4, 3), (1.7, 4), (2.0, 5)],
)
def test_traffic_bucketing(ratio, expected):
    """D-06 ratio bucketing: <1.1=1, <1.3=2, <1.5=3, <1.8=4, >=1.8=5."""
    assert mod._bucket_traffic(ratio) == expected


def test_zone_derivation_ayutthaya_central_2(
    mocker, gmaps_directions_fixture, gmaps_geocode_ayutthaya_fixture
):
    """Pitfall 6: 'Ayutthaya Province' long_name must normalise to 'ayutthaya'."""
    client = _make_client(gmaps_directions_fixture, gmaps_geocode_ayutthaya_fixture)
    mocker.patch.object(mod, "_client", return_value=client)

    result = calculate_route("Bangkok", "Ayutthaya")
    assert result.zone == "central-2"


def test_zone_derivation_lopburi_central_3(
    mocker, gmaps_directions_fixture, gmaps_geocode_lopburi_fixture
):
    client = _make_client(gmaps_directions_fixture, gmaps_geocode_lopburi_fixture)
    mocker.patch.object(mod, "_client", return_value=client)

    result = calculate_route("Bangkok", "Lop Buri")
    assert result.zone == "central-3"


def test_cache_hit_returns_same_object_within_ttl(
    mocker, gmaps_directions_fixture, gmaps_geocode_bangkok_fixture
):
    client = _make_client(gmaps_directions_fixture, gmaps_geocode_bangkok_fixture)
    mocker.patch.object(mod, "_client", return_value=client)

    r1 = calculate_route("Bangkok", "Nonthaburi")
    r2 = calculate_route("Bangkok", "Nonthaburi")

    assert r1 == r2
    # Cached second call — only one directions call total.
    assert client.directions.call_count == 1
    assert client.geocode.call_count == 1


def test_cache_miss_after_ttl_expiry(
    mocker, gmaps_directions_fixture, gmaps_geocode_bangkok_fixture
):
    client = _make_client(gmaps_directions_fixture, gmaps_geocode_bangkok_fixture)
    mocker.patch.object(mod, "_client", return_value=client)

    calculate_route("Bangkok", "Nonthaburi")
    # Jump time forward past TTL (ROUTE_CACHE_TTL_SECONDS = 900).
    mocker.patch(
        "backend.agent.tools._cache.time.time",
        return_value=10**12,  # far-future timestamp
    )
    calculate_route("Bangkok", "Nonthaburi")

    assert client.directions.call_count == 2


def test_no_routes_raises_value_error(
    mocker, gmaps_geocode_bangkok_fixture
):
    client = _make_client([], gmaps_geocode_bangkok_fixture)
    mocker.patch.object(mod, "_client", return_value=client)

    with pytest.raises(ValueError, match="No route"):
        calculate_route("Bangkok", "Nonthaburi")


def test_ungeocodable_destination_raises_value_error(
    mocker, gmaps_directions_fixture
):
    client = _make_client(gmaps_directions_fixture, [])
    mocker.patch.object(mod, "_client", return_value=client)

    with pytest.raises(ValueError):
        calculate_route("Bangkok", "Atlantis")
