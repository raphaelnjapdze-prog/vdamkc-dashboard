import pandas as pd
import pytest

from vdamkc import analysis as a


class TestWhoClassification:
    @pytest.mark.parametrize("mortality, n, expected", [
        (100, 100, a.SUSCEPTIBLE),
        (98.0, 100, a.SUSCEPTIBLE),
        (97.9, 100, a.POSSIBLE),
        (90.0, 100, a.POSSIBLE),
        (89.9, 100, a.CONFIRMED),
        (40.0, 100, a.CONFIRMED),
        # Below 90% but too few mosquitoes to confirm
        (80.0, 50, a.POSSIBLE),
        (None, 100, a.INVALID),
    ])
    def test_thresholds(self, mortality, n, expected):
        assert a.classify_resistance(mortality, n) == expected


class TestAbbott:
    def test_low_control_is_ignored(self):
        assert a.abbott_corrected(92.0, 4.0) == 92.0

    def test_moderate_control_is_corrected(self):
        # (92 - 10) / 90 * 100 = 91.1
        assert a.abbott_corrected(92.0, 10.0) == 91.1

    def test_high_control_invalidates(self):
        assert a.abbott_corrected(92.0, 21.0) is None

    def test_missing_control_means_uncorrected(self):
        assert a.abbott_corrected(92.0, float("nan")) == 92.0

    def test_never_negative(self):
        assert a.abbott_corrected(5.0, 15.0) == 0.0


def _trap(rows):
    return pd.DataFrame(rows, columns=["site_name", "latitude", "longitude", "date",
                                       "collection_method", "species", "count"]).assign(
        date=lambda d: pd.to_datetime(d["date"]))


class TestSiteTrend:
    def test_rising_needs_percent_and_absolute_increase(self):
        trap = _trap([
            ("A", 1, 1, "2026-05-01", "CDC", "x", 2),
            ("A", 1, 1, "2026-06-01", "CDC", "x", 4),     # +100% but only +2
            ("B", 1, 1, "2026-05-01", "CDC", "x", 20),
            ("B", 1, 1, "2026-06-01", "CDC", "x", 30),    # +50% and +10
        ])
        trends = a.site_summary(trap).set_index("site_name")["trend"]
        assert trends["A"] == "Stable"
        assert trends["B"] == "Rising"

    def test_single_collection_has_no_trend(self):
        summary = a.site_summary(_trap([("A", 1, 1, "2026-05-01", "CDC", "x", 50)]))
        assert summary.loc[0, "trend"] == "Single collection"
        assert pd.isna(summary.loc[0, "change_pct"])

    def test_methods_are_not_compared(self):
        trap = _trap([
            ("A", 1, 1, "2026-05-01", "Larval Dip", "x", 5),
            ("A", 1, 1, "2026-06-01", "CDC", "x", 50),
        ])
        assert a.site_summary(trap).loc[0, "trend"] == "Method changed"

    def test_compares_with_last_collection_by_same_method(self):
        trap = _trap([
            ("A", 1, 1, "2026-05-01", "CDC", "x", 10),
            ("A", 1, 1, "2026-05-15", "Larval Dip", "x", 99),
            ("A", 1, 1, "2026-06-01", "CDC", "x", 30),
        ])
        row = a.site_summary(trap).iloc[0]
        assert row["previous_count"] == 10
        assert row["trend"] == "Rising"


class TestRisk:
    def _summary(self, trend, change=None):
        return pd.DataFrame([{"site_name": "A", "latitude": 1, "longitude": 1, "collections": 2,
                              "latest_count": 10, "change_pct": change, "trend": trend}])

    def test_high_needs_rising_and_confirmed(self):
        assert a.risk_table(self._summary("Rising", 50), {"A": a.CONFIRMED}).loc[0, "risk"] == a.HIGH
        assert a.risk_table(self._summary("Rising", 50), {"A": a.POSSIBLE}).loc[0, "risk"] == a.WATCH

    def test_single_collection_is_not_low(self):
        assert a.risk_table(self._summary("Single collection"), {}).loc[0, "risk"] == a.INSUFFICIENT

    def test_bioassay_only_sites_are_listed(self):
        table = a.risk_table(self._summary("Stable", 0), {"B": a.CONFIRMED})
        assert set(table["site_name"]) == {"A", "B"}
        assert table.set_index("site_name").loc["B", "risk"] == a.WATCH


class TestBioassays:
    def test_latest_skips_invalid_tests(self):
        df = pd.DataFrame({
            "site_name": ["A", "A"], "insecticide": ["Delta", "Delta"],
            "date": pd.to_datetime(["2026-05-01", "2026-06-01"]),
            "exposure_time_min": [60, 60], "sample_size": [100, 100],
            "mortality_percent": [85.0, 99.0], "control_mortality_percent": [0.0, 25.0],
        })
        latest = a.latest_bioassays(a.interpret_bioassays(df))
        assert len(latest) == 1
        assert latest.iloc[0]["status"] == a.CONFIRMED
        assert a.resistance_flags(latest) == {"A": a.CONFIRMED}
