"""Memory metric scenario generators."""

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


def _anomaly(pct, bl_pct):
    dev, d = compute_deviation(pct, bl_pct)
    sev, emoji, desc = severity_from_deviation(dev, d)
    finding = AnomalyFinding(
        "memory_available_pct", pct, format_percent(pct),
        bl_pct, format_percent(bl_pct), dev, d, desc,
    )
    return finding, sev, emoji, desc


def gen_memory_normal(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    tgb = rng.choice([8, 16, 32, 64, 128])
    total = tgb * GB
    pct = rng.uniform(40, 70)
    avail = total * pct / 100
    a_pool = [
        f"memory OK, total {tgb}GB, avail {format_bytes(avail)} ({pct:.1f}%), healthy",
        f"memory healthy, avail {pct:.1f}%, {tgb}GB total, {format_bytes(avail)} free",
        f"memory stable, avail {pct:.1f}%, usage within normal range",
    ]
    recs = ["continue monitoring memory trends", "maintain current config", "watch peak-hour memory usage"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "normal", instance=instance,
        time_range=tr, metrics=_mem(total, avail),
        baselines={"mem_avail_pct": pct * rng.uniform(0.95, 1.05)},
        baseline_desc=bd, findings=[], severity="normal",
        status_emoji="\U0001f7e2", status_text="\u6b63\u5e38",
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(2, 3)),
    )


def gen_memory_low_available(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    tgb = rng.choice([8, 16, 32, 64, 128])
    total = tgb * GB
    pct = rng.uniform(8, 15)
    avail = total * pct / 100
    bl = rng.uniform(40, 60)
    finding, sev, emoji, desc = _anomaly(pct, bl)
    a_pool = [
        f"memory avail dropped to {pct:.1f}%, only {format_bytes(avail)} left, baseline {bl:.1f}%",
        f"memory tight, {tgb}GB total, avail {format_bytes(avail)} ({pct:.1f}%), needs attention",
        f"low memory, current {pct:.1f}% below normal {bl:.1f}%, may affect stability",
    ]
    recs = ["identify high-memory processes", "check for memory leaks", "consider adding RAM",
            "optimize app memory usage", "restart memory-heavy services"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=tr, metrics=_mem(total, avail),
        baselines={"mem_avail_pct": bl}, baseline_desc=bd,
        findings=[finding], severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_memory_leak_trend(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    tgb = rng.choice([16, 32, 64, 128])
    total = tgb * GB
    pct = rng.uniform(5, 12)
    avail = total * pct / 100
    bl = rng.uniform(45, 65)
    daily_gb = rng.uniform(0.5, 3.0)
    days = max(1, int(avail / (daily_gb * GB)))
    finding, sev, emoji, desc = _anomaly(pct, bl)
    cap = {"daily_decline": f"{daily_gb:.1f}GB", "days_until_exhaustion": f"{days}", "current_avail": format_bytes(avail)}
    a_pool = [
        f"memory declining, avail from {bl:.1f}% to {pct:.1f}%, daily drop {daily_gb:.1f}GB, ~{days} days left",
        f"suspected memory leak, avail {format_bytes(avail)} declining, ~{days} days until exhaustion",
        f"memory capacity warning: avail {pct:.1f}%, daily drop ~{daily_gb:.1f}GB, act within {days} days",
    ]
    recs = ["investigate memory leak processes", "analyze app memory allocation patterns",
            "deploy memory monitoring alerts", "restart services if needed", "plan memory expansion"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "capacity", instance=instance,
        time_range=tr, metrics=_mem(total, avail),
        baselines={"mem_avail_pct": bl}, baseline_desc=bd,
        findings=[finding], severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
        capacity_info=cap,
    )


def gen_memory_swap_pressure(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    tgb = rng.choice([8, 16, 32, 64])
    total = tgb * GB
    pct = rng.uniform(10, 20)
    avail = total * pct / 100
    bl = rng.uniform(40, 55)
    finding, sev, emoji, desc = _anomaly(pct, bl)
    a_pool = [
        f"memory avail {pct:.1f}%, swap active, memory pressure causing page thrashing, IO impact",
        f"low memory triggered swap, avail only {format_bytes(avail)} ({pct:.1f}%), swap adding disk IO burden",
        f"swap pressure alert: avail memory {pct:.1f}%, heavy paging to disk, system slowing down",
    ]
    recs = ["identify and kill high-memory processes", "add physical memory",
            "tune swappiness parameter", "optimize app memory usage", "enable memory compression (zswap)"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=tr, metrics=_mem(total, avail),
        baselines={"mem_avail_pct": bl}, baseline_desc=bd,
        findings=[finding], severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_memory_oom_risk(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    tgb = rng.choice([8, 16, 32, 64, 128])
    total = tgb * GB
    pct = rng.uniform(1, 5)
    avail = total * pct / 100
    bl = rng.uniform(40, 60)
    finding, sev, emoji, desc = _anomaly(pct, bl)
    a_pool = [
        f"memory nearly exhausted! avail only {format_bytes(avail)} ({pct:.1f}%), OOM kill risk",
        f"critical memory shortage, avail {pct:.1f}%, {tgb}GB total only {format_bytes(avail)} left, OOM imminent",
        f"OOM risk very high, avail memory {pct:.1f}% far below baseline {bl:.1f}%, immediate action needed",
    ]
    recs = ["immediately free memory or restart heavy services", "investigate memory leaks",
            "emergency memory ension", "configure OOM priority to protect critical processes",
            "deploy memory alerts"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=tr, metrics=_mem(total, avail),
        baselines={"mem_avail_pct": bl}, baseline_desc=bd,
        findings=[finding], severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


ALL_GENERATORS = [
    gen_memory_normal, gen_memory_low_available, gen_memory_leak_trend,
    gen_memory_swap_pressure, gen_memory_oom_risk,
]
