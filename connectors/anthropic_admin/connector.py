"""Anthropic Admin connector: organization usage buckets into neutral Observations.

The Usage & Cost Admin API (``GET /v1/organizations/usage_report/messages``, ``x-api-key``
admin key + ``anthropic-version``; verified docs.anthropic 2026-06-08) wraps time buckets under
top-level ``data``: ``{starting_at, ending_at, results: [{model, workspace_id, api_key_id,
service_tier, uncached_input_tokens, cache_read_input_tokens, cache_creation:
{ephemeral_1h_input_tokens, ephemeral_5m_input_tokens}, output_tokens}]}``. The grouping
dimensions are **opaque ids** — no user PII. ``parse_usage`` summarizes a bucket's token totals
(input = uncached + cache-read + the nested cache-creation tokens) + distinct models; the opaque
``workspace_id``/``api_key_id`` are not surfaced. Poll-only — no webhooks; the live REST poll +
admin-key resolution stay in the operator runtime (see ``auth.md``).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation

_INPUT_KEYS = ("uncached_input_tokens", "cache_read_input_tokens")
# verified docs.anthropic 2026-06-08: cache-creation tokens are NESTED under
# `cache_creation`, not a flat `cache_creation_input_tokens` (which does not exist).
_CACHE_CREATION_KEYS = ("ephemeral_1h_input_tokens", "ephemeral_5m_input_tokens")


def _int(value: object) -> int:
    """Coerce a token metric to int (0 when absent / non-numeric; ``bool`` is not a metric)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _cache_creation_tokens(row: dict) -> int:
    """Sum the nested cache-creation input tokens (`cache_creation.ephemeral_*`)."""
    cc = row.get("cache_creation")
    if not isinstance(cc, dict):
        return 0
    return sum(_int(cc.get(key)) for key in _CACHE_CREATION_KEYS)


def _sum_tokens(results: list) -> tuple[int, int, list[str]]:
    """Total input/output tokens and collect distinct model names across a bucket."""
    in_tokens = 0
    out_tokens = 0
    models: list[str] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        in_tokens += sum(_int(row.get(key)) for key in _INPUT_KEYS) + _cache_creation_tokens(row)
        out_tokens += _int(row.get("output_tokens"))
        model = row.get("model")
        if isinstance(model, str) and model and model not in models:
            models.append(model)
    return in_tokens, out_tokens, models


def parse_usage(bucket: dict) -> Observation:
    """Map an Anthropic usage bucket into a PII-free aggregate Observation."""
    start = (bucket.get("starting_at") or "").strip()
    raw = bucket.get("results")
    results = raw if isinstance(raw, list) else []
    in_tokens, out_tokens, models = _sum_tokens(results)
    return Observation(
        source_ref=SourceRef(
            source_id="anthropic_admin",
            ref=f"anthropic:usage:{start}" if start else "anthropic-usage",
            kind="usage_metrics",
        ),
        excerpt=(
            f"Anthropic usage {start or 'report'}: {in_tokens} input / {out_tokens} output "
            f"tokens across {len(results)} group(s); models {', '.join(models) if models else '—'}"
        ),
        mode=SourceMode.ACTIVE,
        title=f"Anthropic usage {start}".strip(),
    )


class AnthropicAdminConnector:
    """Anthropic Admin connector identity plus the usage parse surface (active poll only)."""

    source_id = "anthropic_admin"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.ACTIVE}))

    def can_handle_ref(self, ref: SourceRef) -> bool:
        return ref.source_id == "anthropic_admin"

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_usage(payload)]
