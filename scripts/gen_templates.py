#!/usr/bin/env python3
"""Generate all template files for the inspection_lora project."""

import sys
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "data" / "templates"


def write_memory():
    code = '''"""Memory metric scenario generators."""

import random

from inspection_lora.data_utils import (
    AnomalyFinding, MetricSample, ScenarioConfig,
    compute_deviation, format_bytes, format_percent,
    random_baseline_desc, random_instance, random_time_range,
    severity_from_deviation,
)

GB = 1024 ** 3


def _mem(total_bytes, avail_bytes):
    return [
        MetricSample("node_memory_MemTotal_bytes", {}, total_bytes, format_bytes(total_bytes)),
        MetricSample("node_memory_MemAvailable_bytes", {}, avail_bytes, format_bytes(avail_bytes)),
    ]


def gen_memory_normal(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    time_range = random_time_range(rng)
    baseline_desc = random_baseline_desc(rng)
    total_gb = rng.choice([8, 16, 32, 64, 128])
    total = total_gb * GB
    pct = rng.uniform(40, 70)
    avail = total * pct / 100
    metrics = _mem(total, avail)
    baselines = {"mem_avail_pct": pct * rng.uniform(0.95, 1.05)}
    a = [
        f"\\u5185\\u5b58\\u72b6\\u6001\\u6b63\\u5e38\\uff0c\\u603b\\u91cf {total_gb}GB\\uff0c\\u53ef\\u7528 {format_bytes(avail)}\\uff08{pct:.1f}%\\uff09\\uff0c\\u8d44\\u6e90\\u5145\\u8db3\\u3002",
        f"\\u5185\\u5b58\\u4f7f\\u7528\\u5065\\u5eb7\\uff0c\\u53ef\\u7528\\u7387 {pct:.1f}%\\uff0c{total_gb}GB \\u603b\\u91cf\\u4e2d\\u5269\\u4f59 {format_bytes(avail)}\\uff0c\\u65e0\\u5f02\\u5e38\\u3002",
        f"\\u7cfb\\u7edf\\u5185\\u5b58\\u8fd0\\u884c\\u5e73\\u7a33\\uff0c\\u53ef\\u7528 {pct:.1f}%\\uff0c\\u4f7f\\u7528\\u7387\\u5728\\u6b63\\u5e38\\u8303\\u56f4\\u5185\\u3002",
    ]
    recs = ["\\u7ee7\\u7eed\\u76d1\\u63a7\\u5185\\u5b58\\u4f7f\\u7528\\u8d8b\\u52bf", "\\u4fdd\\u6301\\u5f53\\u524d\\u914d\\u7f6e", "\\u5173\\u6ce8\\u4e1a\\u52a1\\u9ad8\\u5cf0\\u671f\\u5185\\u5b58\\u53d8\\u5316"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "normal", instance=instance,
        time_range=time_range, metrics=metrics, baselines=baselines,
        baseline_desc=baseline_desc, findings=[], severity="normal",
        status_emoji="\\U0001f7e2", status_text="\\u6b63\\u5e38",
        analysis=rng.choice(a), recommendations=rng.sample(recs, k=rng.randint(2, 3)),
    )
'''
    # This approach with unicode escapes is too painful. Let me just write raw Chinese.
    pass


# Actually, let me just write the files directly with Path.write_text
# using triple-quoted strings in Python, which avoids all JSON issues.


def main():
    write_all_templates()


def write_all_templates():
    # Memory templates
    mem_code = (
        '"""Memory metric scenario generators."""\n'
        "\n"
        "import random\n"
        "\n"
        "from inspection_lora.data_utils import (\n"
        "    AnomalyFinding, MetricSample, ScenarioConfig,\n"
        "    compute_deviation, format_bytes, format_percent,\n"
        "    random_baseline_desc, random_instance, random_time_range,\n"
        "    severity_from_deviation,\n"
        ")\n"
        "\n"
        "GB = 1024 ** 3\n"
    )
    # This is also getting unwieldy. Let me just use a simpler approach.
    pass


if __name__ == "__main__":
    main()
