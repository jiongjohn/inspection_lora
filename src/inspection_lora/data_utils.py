"""
Shared foundation module for Prometheus metrics AI inspection data generation pipeline.
Provides dataclasses, constants, and helper functions for generating training data.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import random
from pathlib import Path


SYSTEM_PROMPT = "你是一个专业的基础设施监控助手,负责分析 Prometheus 指标数据并提供巡检报告。请根据提供的指标数据进行分析,识别异常,给出判断和建议。"

INSTANCE_POOL = [
    "node-web-01:9100",
    "node-api-01:9100",
    "node-db-master-01:9100",
    "node-db-slave-01:9100",
    "node-cache-01:9100",
    "node-mq-01:9100",
    "node-gateway-01:9100",
    "node-monitor-01:9100",
    "node-log-01:9100",
    "node-search-01:9100",
    "node-batch-01:9100",
    "node-app-01:9100",
    "node-proxy-01:9100",
    "node-storage-01:9100",
    "node-compute-01:9100",
    "node-web-02:9100",
    "node-web-03:9100",
    "node-api-02:9100",
    "node-app-02:9100",
    "node-app-03:9100",
    "node-db-slave-02:9100",
    "node-cache-02:9100",
    "node-mq-02:9100",
    "node-batch-02:9100",
    "node-storage-02:9100",
    "node-compute-02:9100",
    "node-compute-03:9100",
    "node-gateway-02:9100",
    "node-proxy-02:9100",
    "node-log-02:9100",
]

BASELINE_DESCS = [
    "过去7天平均",
    "过去30天平均",
    "过去24小时平均",
    "过去7天P95",
    "过去30天P95",
]

SCENARIO_TYPES = [
    "single_anomaly",
    "multi_metric",
    "normal",
    "capacity",
    "health",
    "report",
]


@dataclass
class MetricSample:
    """Represents a single Prometheus metric sample."""
    name: str
    labels: dict[str, str]
    value: float
    display_value: str


@dataclass
class AnomalyFinding:
    """Represents an anomaly detection finding."""
    metric_name: str
    current_value: float
    current_display: str
    baseline_value: float
    baseline_display: str
    deviation_percent: float
    direction: str
    severity_desc: str


@dataclass
class ScenarioConfig:
    """Configuration for a complete inspection scenario."""
    scenario_type: str
    instance: str
    time_range: tuple[str, str]
    metrics: list[MetricSample]
    baselines: dict[str, float]
    baseline_desc: str
    findings: list[AnomalyFinding]
    severity: str
    status_emoji: str
    status_text: str
    analysis: str
    recommendations: list[str]
    health_score: int | None = None
    capacity_info: dict | None = None


def random_instance(rng: random.Random) -> str:
    """Select a random instance from the pool."""
    return rng.choice(INSTANCE_POOL)


def random_time_range(rng: random.Random) -> tuple[str, str]:
    """Generate a realistic time range within the last 30 days."""
    base_date = datetime(2026, 2, 25)
    days_ago = rng.randint(0, 29)
    target_date = base_date - timedelta(days=days_ago)
    
    start_hour = rng.randint(0, 23)
    start_minute = rng.choice([0, 15, 30, 45])
    
    duration_minutes = rng.randint(15, 120)
    
    start_time = target_date.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=duration_minutes)
    
    return (
        start_time.strftime("%Y-%m-%d %H:%M"),
        end_time.strftime("%Y-%m-%d %H:%M"),
    )


def random_baseline_desc(rng: random.Random) -> str:
    """Select a random baseline description."""
    return rng.choice(BASELINE_DESCS)


def compute_deviation(current: float, baseline: float) -> tuple[float, str]:
    """Compute deviation percentage and direction."""
    deviation_percent = abs(current - baseline) / baseline * 100 if baseline != 0 else 0.0
    direction = "上升" if current > baseline else "下降"
    return (round(deviation_percent, 1), direction)


def severity_from_deviation(deviation_percent: float, direction: str = "上升") -> tuple[str, str, str]:
    """Determine severity level from deviation percentage."""
    if deviation_percent < 10:
        return ("normal", "🟢", "正常范围")
    elif deviation_percent < 30:
        trend = "偏高" if direction == "上升" else "偏低"
        return ("warning", "🟡", f"轻微{trend}")
    elif deviation_percent < 60:
        trend = "偏高" if direction == "上升" else "偏低"
        return ("warning", "🟡", f"明显{trend}")
    else:
        trend = "偏高" if direction == "上升" else "偏低"
        return ("critical", "🔴", f"严重{trend}")


def format_bytes(value_bytes: float) -> str:
    """Convert bytes to human-readable format."""
    if value_bytes < 1024:
        return f"{int(value_bytes)} B"
    elif value_bytes < 1024 ** 2:
        return f"{int(value_bytes / 1024)} KB"
    elif value_bytes < 1024 ** 3:
        return f"{value_bytes / (1024 ** 2):.1f} MB"
    elif value_bytes < 1024 ** 4:
        return f"{value_bytes / (1024 ** 3):.1f} GB"
    else:
        return f"{value_bytes / (1024 ** 4):.1f} TB"


def format_percent(value: float) -> str:
    """Format a value as a percentage."""
    return f"{value:.1f}%"


def write_jsonl(filepath: str | Path, records: list[dict]) -> int:
    """Write records to a JSONL file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    return len(records)


def read_jsonl(filepath: str | Path) -> list[dict]:
    """Read records from a JSONL file."""
    filepath = Path(filepath)
    records = []
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    
    return records
