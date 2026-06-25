"""Tests for Week 3 delivery-rate calculations."""

import pytest

from scripts.measure_delivery_rate import compute_report, expected_published


def test_expected_published_from_feed_count():
    assert expected_published(feeds=8, interval_seconds=5, duration_seconds=3600) == 5760


def test_compute_report_rates():
    report = compute_report(published=100, processed=97, succeeded=95, failed=2, dlq=1)

    assert report.delivery_rate == pytest.approx(0.97)
    assert report.success_rate == pytest.approx(0.95)
    assert report.failure_rate == pytest.approx(0.02)
    assert report.dlq == 1


def test_compute_report_rejects_negative_counts():
    with pytest.raises(ValueError):
        compute_report(published=1, processed=-1, succeeded=0, failed=0)
