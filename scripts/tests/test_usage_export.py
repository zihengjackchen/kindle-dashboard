import importlib.util
from datetime import datetime, timezone
from pathlib import Path


def test_usage_export_excludes_account_credentials_and_raw_threads():
    path = Path(__file__).resolve().parents[1]/"export-chatgpt.py"
    spec = importlib.util.spec_from_file_location("usage_export", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    record = module.usage_record(
        {"summary": {"lifetimeTokens": 123456, "peakDailyTokens": 9000, "currentStreakDays": 3}, "threadUsage": [{"secret": "private-thread"}]},
        {"accountId": "private-account", "rateLimits": {"limitId": "codex", "primary": {"usedPercent": 5, "windowDurationMins": 10080, "resetsAt": 1800000000}}},
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    assert record.lifetime_tokens == 123456 and record.used_percent == 5
    assert record.limit_name == "Codex 7d"
    assert record.valid_until.timestamp()-record.as_of.timestamp() == 7200
    assert "private" not in record.model_dump_json()
    assert "threadUsage" not in record.model_dump_json()
