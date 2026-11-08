from datetime import datetime, timedelta, timezone
from time import monotonic

import pytest
from prometheus_client import REGISTRY

import hangarllm
from hangarllm.integrations.prometheus import PrometheusLogger
from hangarllm.integrations.prometheus_helpers import bounded_prometheus_series_tracker
from hangarllm.integrations.prometheus_helpers.bounded_prometheus_series_tracker import (
    BoundedPrometheusSeriesTracker,
)
from hangarllm.types.integrations.prometheus import UserAPIKeyLabelValues


@pytest.fixture(autouse=True)
def cleanup_prometheus_registry():
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass

    old_enable_end_user = hangarllm.enable_end_user_cost_tracking_prometheus_only
    old_metrics_config = hangarllm.prometheus_metrics_config
    old_max_series = hangarllm.prometheus_end_user_metrics_max_series_per_metric
    old_ttl_seconds = hangarllm.prometheus_end_user_metrics_ttl_seconds
    old_cleanup_interval_seconds = (
        hangarllm.prometheus_end_user_metrics_cleanup_interval_seconds
    )

    yield

    hangarllm.enable_end_user_cost_tracking_prometheus_only = old_enable_end_user
    hangarllm.prometheus_metrics_config = old_metrics_config
    hangarllm.prometheus_end_user_metrics_max_series_per_metric = old_max_series
    hangarllm.prometheus_end_user_metrics_ttl_seconds = old_ttl_seconds
    hangarllm.prometheus_end_user_metrics_cleanup_interval_seconds = (
        old_cleanup_interval_seconds
    )

    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass


def test_prometheus_end_user_series_are_capped_per_metric():
    hangarllm.enable_end_user_cost_tracking_prometheus_only = True
    hangarllm.prometheus_metrics_config = [
        {
            "group": "end-user-spend",
            "metrics": ["hangarllm_spend_metric"],
            "include_labels": ["end_user"],
        }
    ]
    hangarllm.prometheus_end_user_metrics_max_series_per_metric = 3
    hangarllm.prometheus_end_user_metrics_ttl_seconds = None
    logger = PrometheusLogger()

    for index in range(6):
        PrometheusLogger._inc_labeled_counter(
            logger,
            logger.hangarllm_spend_metric,
            "hangarllm_spend_metric",
            UserAPIKeyLabelValues(end_user=f"end-user-{index}"),
            amount=0.01,
        )

    assert len(logger.hangarllm_spend_metric._metrics) == 3
    assert set(logger.hangarllm_spend_metric._metrics) == {
        ("end-user-3",),
        ("end-user-4",),
        ("end-user-5",),
    }


def test_bounded_prometheus_series_tracker_is_label_agnostic():
    class FakeMetric:
        def __init__(self):
            self.removed_label_values = []

        def remove(self, *label_values):
            self.removed_label_values.append(label_values)

    metric = FakeMetric()
    tracker = BoundedPrometheusSeriesTracker()

    for index in range(4):
        tracker.track_series(
            metric=metric,
            metric_name="generic_metric",
            label_values=(f"route-{index}", "200"),
            max_series=2,
            ttl_seconds=None,
            cleanup_interval_seconds=60.0,
        )

    assert metric.removed_label_values == [
        ("route-0", "200"),
        ("route-1", "200"),
    ]


def test_bounded_prometheus_series_tracker_treats_zero_max_as_unlimited():
    # A misconfigured ``max_series=0`` must not silently evict every emission.
    class FakeMetric:
        def __init__(self):
            self.removed_label_values = []

        def remove(self, *label_values):
            self.removed_label_values.append(label_values)

    metric = FakeMetric()
    tracker = BoundedPrometheusSeriesTracker()

    for index in range(3):
        tracker.track_series(
            metric=metric,
            metric_name="generic_metric",
            label_values=(f"end-user-{index}",),
            max_series=0,
            ttl_seconds=None,
            cleanup_interval_seconds=60.0,
        )

    assert metric.removed_label_values == []


def test_prometheus_end_user_series_expire_by_ttl(monkeypatch):
    hangarllm.enable_end_user_cost_tracking_prometheus_only = True
    hangarllm.prometheus_metrics_config = [
        {
            "group": "end-user-spend",
            "metrics": ["hangarllm_spend_metric"],
            "include_labels": ["end_user"],
        }
    ]
    hangarllm.prometheus_end_user_metrics_max_series_per_metric = None
    hangarllm.prometheus_end_user_metrics_ttl_seconds = 10.0
    hangarllm.prometheus_end_user_metrics_cleanup_interval_seconds = 0.0
    logger = PrometheusLogger()

    current_time = [monotonic()]
    monkeypatch.setattr(
        bounded_prometheus_series_tracker.time,
        "monotonic",
        lambda: current_time[0],
    )
    PrometheusLogger._inc_labeled_counter(
        logger,
        logger.hangarllm_spend_metric,
        "hangarllm_spend_metric",
        UserAPIKeyLabelValues(end_user="stale-end-user"),
        amount=0.01,
    )

    current_time[0] += 11.0
    PrometheusLogger._inc_labeled_counter(
        logger,
        logger.hangarllm_spend_metric,
        "hangarllm_spend_metric",
        UserAPIKeyLabelValues(end_user="fresh-end-user"),
        amount=0.01,
    )

    assert set(logger.hangarllm_spend_metric._metrics) == {("fresh-end-user",)}


def test_prometheus_end_user_not_tracked_by_default():
    hangarllm.enable_end_user_cost_tracking_prometheus_only = None
    labels = PrometheusLogger().get_labels_for_metric("hangarllm_spend_metric")
    assert "end_user" in labels

    label_values = UserAPIKeyLabelValues(end_user="not-exported")
    from hangarllm.integrations.prometheus import prometheus_label_factory

    prometheus_labels = prometheus_label_factory(labels, label_values)
    assert prometheus_labels["end_user"] is None


def test_prometheus_customer_budget_series_are_capped_per_metric(monkeypatch):
    monkeypatch.setattr(hangarllm, "enable_end_user_cost_tracking_prometheus_only", True)
    monkeypatch.setattr(hangarllm, "prometheus_end_user_metrics_max_series_per_metric", 2)
    monkeypatch.setattr(hangarllm, "prometheus_end_user_metrics_ttl_seconds", None)
    logger = PrometheusLogger()

    for index in range(5):
        logger._set_customer_budget_metrics(
            end_user_id=f"customer-{index}",
            spend=1.0,
            max_budget=10.0,
            budget_reset_at=None,
        )

    assert set(logger.hangarllm_remaining_customer_budget_metric._metrics) == {("customer-3",), ("customer-4",)}
    assert set(logger.hangarllm_customer_max_budget_metric._metrics) == {("customer-3",), ("customer-4",)}


def test_prometheus_customer_budget_series_expire_by_ttl(monkeypatch):
    monkeypatch.setattr(hangarllm, "enable_end_user_cost_tracking_prometheus_only", True)
    monkeypatch.setattr(hangarllm, "prometheus_end_user_metrics_max_series_per_metric", None)
    monkeypatch.setattr(hangarllm, "prometheus_end_user_metrics_ttl_seconds", 10.0)
    monkeypatch.setattr(hangarllm, "prometheus_end_user_metrics_cleanup_interval_seconds", 0.0)
    logger = PrometheusLogger()

    current_time = [monotonic()]
    monkeypatch.setattr(bounded_prometheus_series_tracker.time, "monotonic", lambda: current_time[0])
    logger._set_customer_budget_metrics(
        end_user_id="customer-with-removed-budget",
        spend=1.0,
        max_budget=10.0,
        budget_reset_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    current_time[0] += 11.0
    logger._set_customer_budget_metrics(
        end_user_id="customer-still-budgeted",
        spend=1.0,
        max_budget=10.0,
        budget_reset_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    assert set(logger.hangarllm_remaining_customer_budget_metric._metrics) == {("customer-still-budgeted",)}
    assert set(logger.hangarllm_customer_max_budget_metric._metrics) == {("customer-still-budgeted",)}
    assert set(logger.hangarllm_customer_budget_remaining_hours_metric._metrics) == {("customer-still-budgeted",)}
