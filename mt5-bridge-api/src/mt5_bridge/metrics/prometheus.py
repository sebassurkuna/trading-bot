"""Custom Prometheus metrics for the MT5 Bridge API."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# ---------------------------------------------------------------------------
# Histogram: end-to-end order latency in milliseconds.
# Labels:
#   operation — open | close | modify
# ---------------------------------------------------------------------------
ORDER_LATENCY = Histogram(
    name="mt5_gateway_order_latency_ms",
    documentation="End-to-end latency of MT5 order operations in milliseconds.",
    labelnames=["operation"],
    buckets=[10, 25, 50, 100, 250, 500, 1_000, 2_500, 5_000],
)

# ---------------------------------------------------------------------------
# Counter: total order outcomes (success vs failure).
# Labels:
#   operation — open | close | modify
#   outcome   — success | failure
# ---------------------------------------------------------------------------
ORDER_OUTCOME = Counter(
    name="mt5_gateway_success_rate",
    documentation="Count of MT5 order operations segmented by outcome.",
    labelnames=["operation", "outcome"],
)

# ---------------------------------------------------------------------------
# Counter: rejected duplicate order attempts (idempotency guard hits).
# Labels:
#   symbol — MT5 symbol of the duplicate request
# ---------------------------------------------------------------------------
DUPLICATE_ORDER_ATTEMPTS = Counter(
    name="duplicate_order_attempts",
    documentation="Count of order requests rejected as duplicates by the idempotency guard.",
    labelnames=["symbol"],
)
