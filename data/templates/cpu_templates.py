"""CPU 指标场景生成器。"""

import random

from inspection_lora.data_utils import (
    AnomalyFinding,
    MetricSample,
    ScenarioConfig,
    compute_deviation,
    format_percent,
    random_baseline_desc,
    random_instance,
    random_time_range,
    severity_from_deviation,
)


def _norm(rng, idle, user, system, iowait):
    """归一化 CPU 各模式到 100%，补充小模式。"""
    nice = rng.uniform(0, 0.8)
    irq = rng.uniform(0, 0.4)
    softirq = rng.uniform(0, 0.8)
    steal = rng.uniform(0, 0.3)
    total = idle + user + system + iowait + nice + irq + softirq + steal
    f = 100.0 / total
    return {
        "idle": idle * f, "user": user * f, "system": system * f,
        "iowait": iowait * f, "nice": nice * f, "irq": irq * f,
        "softirq": softirq * f, "steal": steal * f,
    }


def _cpu_metrics(m, load1, load5, load15):
    """构建 CPU MetricSample 列表。"""
    samples = []
    for mode in ("user", "system", "idle", "iowait", "nice", "irq", "softirq", "steal"):
        samples.append(MetricSample(
            "node_cpu_seconds_total", {"cpu": "0", "mode": mode},
            m[mode], format_percent(m[mode]),
        ))
    samples.append(MetricSample("node_load1", {}, load1, f"{load1:.2f}"))
    samples.append(MetricSample("node_load5", {}, load5, f"{load5:.2f}"))
    samples.append(MetricSample("node_load15", {}, load15, f"{load15:.2f}"))
    return samples


def gen_cpu_normal(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    time_range = random_time_range(rng)
    baseline_desc = random_baseline_desc(rng)
    cores = rng.choice([4, 8, 16, 32])
    m = _norm(rng, rng.uniform(60, 80), rng.uniform(15, 30), rng.uniform(3, 8), rng.uniform(0.5, 3))
    load1 = rng.uniform(0.3, cores * 0.5)
    load5 = load1 * rng.uniform(0.9, 1.1)
    load15 = load1 * rng.uniform(0.85, 1.05)
    metrics = _cpu_metrics(m, load1, load5, load15)
    baselines = {"cpu_user": m["user"] * rng.uniform(0.95, 1.05), "load1": load1 * rng.uniform(0.9, 1.1)}
    analysis_pool = [
        f"CPU 使用率正常，空闲 {m['idle']:.1f}%，用户态 {m['user']:.1f}%，系统态 {m['system']:.1f}%，负载 {load1:.2f} 低于 {cores} 核阈值。",
        f"CPU 状态健康，空闲资源充足（{m['idle']:.1f}%），用户态 {m['user']:.1f}%，IO 等待仅 {m['iowait']:.1f}%。",
        f"CPU 运行平稳，{cores} 核系统负载 {load1:.2f}，空闲 {m['idle']:.1f}%，无异常波动。",
        f"系统 CPU 平稳运行，用户态 {m['user']:.1f}%、系统态 {m['system']:.1f}% 均在正常范围。",
    ]
    recs = ["继续保持当前配置", "定期监控 CPU 趋势变化", "可适当增加业务负载", "保持现有资源配置"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "normal", instance=instance,
        time_range=time_range, metrics=metrics, baselines=baselines,
        baseline_desc=baseline_desc, findings=[], severity="normal",
        status_emoji="🟢", status_text="正常",
        analysis=rng.choice(analysis_pool),
        recommendations=rng.sample(recs, k=rng.randint(2, 3)),
    )


def gen_cpu_spike(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    time_range = random_time_range(rng)
    baseline_desc = random_baseline_desc(rng)
    cores = rng.choice([4, 8, 16, 32])
    m = _norm(rng, rng.uniform(2, 10), rng.uniform(80, 95), rng.uniform(3, 8), rng.uniform(0.5, 2))
    load1 = rng.uniform(cores * 2.5, cores * 5)
    load5 = load1 * rng.uniform(0.6, 0.9)
    load15 = load1 * rng.uniform(0.4, 0.7)
    bl_user = rng.uniform(15, 25)
    bl_load = rng.uniform(0.5, cores * 1.5)
    metrics = _cpu_metrics(m, load1, load5, load15)
    baselines = {"cpu_user": bl_user, "load1": bl_load}
    u_dev, u_dir = compute_deviation(m["user"], bl_user)
    l_dev, l_dir = compute_deviation(load1, bl_load)
    sev, emoji, sev_desc = severity_from_deviation(max(u_dev, l_dev), "上升")
    findings = [
        AnomalyFinding("CPU 用户态", m["user"], format_percent(m["user"]), bl_user, format_percent(bl_user), u_dev, u_dir, sev_desc),
        AnomalyFinding("1 分钟负载", load1, f"{load1:.2f}", bl_load, f"{bl_load:.2f}", l_dev, l_dir, sev_desc),
    ]
    analysis_pool = [
        f"CPU 突增异常！用户态飙升至 {m['user']:.1f}%，空闲骤降至 {m['idle']:.1f}%，负载 {load1:.2f} 远超 {cores} 核容量。",
        f"CPU 使用率突然激增，用户态 {m['user']:.1f}% 接近满载，负载 {load1:.2f} 是核心数的 {load1/cores:.1f} 倍。",
        f"严重 CPU 压力！用户态 {m['user']:.1f}%，空闲不足 {m['idle']:.1f}%，load1={load1:.2f} 大量进程等待调度。",
        f"CPU 突发高负载，用户态从基线 {bl_user:.1f}% 暴涨至 {m['user']:.1f}%，负载从 {bl_load:.2f} 飙升至 {load1:.2f}。",
    ]
    recs = ["立即排查高 CPU 进程（top/htop）", "检查是否有异常任务或死循环", "分析应用日志定位突增原因",
            "考虑限流或扩容", "监控是否为定时任务引发", "评估是否需要紧急重启服务"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=time_range, metrics=metrics, baselines=baselines,
        baseline_desc=baseline_desc, findings=findings, severity=sev,
        status_emoji=emoji, status_text=sev_desc,
        analysis=rng.choice(analysis_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_cpu_sustained_high(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    time_range = random_time_range(rng)
    baseline_desc = random_baseline_desc(rng)
    cores = rng.choice([4, 8, 16, 32])
    m = _norm(rng, rng.uniform(10, 25), rng.uniform(55, 75), rng.uniform(5, 12), rng.uniform(1, 5))
    load1 = rng.uniform(cores * 1.8, cores * 3)
    load5 = load1 * rng.uniform(0.95, 1.05)
    load15 = load1 * rng.uniform(0.9, 1.1)
    bl_user = rng.uniform(20, 35)
    metrics = _cpu_metrics(m, load1, load5, load15)
    baselines = {"cpu_user": bl_user, "load1": rng.uniform(0.8, cores * 1.5)}
    u_dev, u_dir = compute_deviation(m["user"], bl_user)
    sev, emoji, sev_desc = severity_from_deviation(u_dev, "上升")
    findings = [
        AnomalyFinding("CPU 用户态", m["user"], format_percent(m["user"]), bl_user, format_percent(bl_user), u_dev, u_dir, sev_desc),
    ]
    analysis_pool = [
        f"CPU 持续偏高，用户态 {m['user']:.1f}% 长期高于基线 {bl_user:.1f}%，空闲 {m['idle']:.1f}%，负载 {load1:.2f} 持续超标。",
        f"CPU 长时间高负载，用户态 {m['user']:.1f}%，空闲仅 {m['idle']:.1f}%，load5={load5:.2f} 和 load15={load15:.2f} 接近，非瞬时波动。",
        f"CPU 资源紧张，用户态 {m['user']:.1f}% 持续偏高，空闲率从基线降至 {m['idle']:.1f}%，1/5/15 分钟负载均超标。",
    ]
    recs = ["分析业务增长趋势评估扩容需求", "优化应用代码降低 CPU 密集计算", "检查是否有低效算法或循环",
            "考虑水平扩展或垂直升级", "启用缓存减少重复计算", "分析慢查询和热点代码路径"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=time_range, metrics=metrics, baselines=baselines,
        baseline_desc=baseline_desc, findings=findings, severity=sev,
        status_emoji=emoji, status_text=sev_desc,
        analysis=rng.choice(analysis_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_cpu_iowait_high(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    time_range = random_time_range(rng)
    baseline_desc = random_baseline_desc(rng)
    cores = rng.choice([4, 8, 16, 32])
    m = _norm(rng, rng.uniform(5, 20), rng.uniform(15, 35), rng.uniform(5, 15), rng.uniform(30, 60))
    load1 = rng.uniform(cores * 1.5, cores * 3.5)
    load5 = load1 * rng.uniform(0.9, 1.1)
    load15 = load1 * rng.uniform(0.85, 1.05)
    bl_iowait = rng.uniform(1, 5)
    metrics = _cpu_metrics(m, load1, load5, load15)
    baselines = {"cpu_iowait": bl_iowait, "load1": rng.uniform(0.5, cores * 1.5)}
    iw_dev, iw_dir = compute_deviation(m["iowait"], bl_iowait)
    sev, emoji, sev_desc = severity_from_deviation(iw_dev, "上升")
    findings = [
        AnomalyFinding("CPU IO 等待", m["iowait"], format_percent(m["iowait"]), bl_iowait, format_percent(bl_iowait), iw_dev, iw_dir, sev_desc),
    ]
    analysis_pool = [
        f"严重 IO 瓶颈！CPU IO 等待高达 {m['iowait']:.1f}%，远超基线 {bl_iowait:.1f}%，大量进程阻塞在磁盘 IO 上。",
        f"磁盘 IO 性能问题，{m['iowait']:.1f}% 异常偏高，CPU 空闲 {m['idle']:.1f}% 但无法有效利用。",
        f"IO 等待占用 {m['iowait']:.1f}%，从基线 {bl_iowait:.1f}% 暴涨，磁盘成为瓶颈，负载 {load1:.2f}。",
    ]
    recs = ["使用 iostat/iotop 排查磁盘 IO 瓶颈", "检查是否有大量随机读写操作", "评估磁盘 IOPS 是否达到上限",
            "考虑升级到 SSD 或优化存储架构", "优化数据库查询减少磁盘访问", "检查是否有磁盘故障或降级"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=time_range, metrics=metrics, baselines=baselines,
        baseline_desc=baseline_desc, findings=findings, severity=sev,
        status_emoji=emoji, status_text=sev_desc,
        analysis=rng.choice(analysis_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_cpu_system_high(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    time_range = random_time_range(rng)
    baseline_desc = random_baseline_desc(rng)
    cores = rng.choice([4, 8, 16, 32])
    m = _norm(rng, rng.uniform(5, 20), rng.uniform(15, 30), rng.uniform(40, 65), rng.uniform(1, 5))
    load1 = rng.uniform(cores * 1.5, cores * 3)
    load5 = load1 * rng.uniform(0.9, 1.1)
    load15 = load1 * rng.uniform(0.85, 1.05)
    bl_sys = rng.uniform(3, 10)
    metrics = _cpu_metrics(m, load1, load5, load15)
    baselines = {"cpu_system": bl_sys, "load1": rng.uniform(0.5, cores * 1.5)}
    s_dev, s_dir = compute_deviation(m["system"], bl_sys)
    sev, emoji, sev_desc = severity_from_deviation(s_dev, "上升")
    findings = [
        AnomalyFinding("CPU 系统态", m["system"], format_percent(m["system"]), bl_sys, format_percent(bl_sys), s_dev, s_dir, sev_desc),
    ]
    analysis_pool = [
        f"内核态 CPU 异常偏高！系统态 {m['system']:.1f}% 远超基线 {bl_sys:.1f}%，可能存在大量系统调用或内核级问题。",
        f"系统态 CPU 占用 {m['system']:.1f}%，正常基线仅 {bl_sys:.1f}%，softirq={m['softirq']:.1f}% 也偏高，可能有网络中断风暴。",
        f"CPU 系统态异常，从 {bl_sys:.1f}% 升至 {m['system']:.1f}%，空闲 {m['idle']:.1f}%，需排查内核级瓶颈。",
    ]
    recs = ["使用 perf top 分析内核热点函数", "检查是否有大量上下文切换（vmstat）",
            "排查网络中断风暴（/proc/interrupts）", "检查内核日志（dmesg）是否有异常",
            "评估是否有驱动或内核模块问题", "考虑升级内核版本"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=time_range, metrics=metrics, baselines=baselines,
        baseline_desc=baseline_desc, findings=findings, severity=sev,
        status_emoji=emoji, status_text=sev_desc,
        analysis=rng.choice(analysis_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_cpu_load_mismatch(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    time_range = random_time_range(rng)
    baseline_desc = random_baseline_desc(rng)
    cores = rng.choice([4, 8, 16, 32])
    m = _norm(rng, rng.uniform(30, 50), rng.uniform(25, 45), rng.uniform(5, 12), rng.uniform(5, 15))
    load1 = rng.uniform(cores * 3, cores * 8)
    load5 = load1 * rng.uniform(0.85, 1.0)
    load15 = load1 * rng.uniform(0.7, 0.95)
    bl_load = rng.uniform(0.5, cores * 1.5)
    metrics = _cpu_metrics(m, load1, load5, load15)
    baselines = {"load1": bl_load}
    l_dev, l_dir = compute_deviation(load1, bl_load)
    sev, emoji, sev_desc = severity_from_deviation(l_dev, "上升")
    findings = [
        AnomalyFinding("1 分钟负载", load1, f"{load1:.2f}", bl_load, f"{bl_load:.2f}", l_dev, l_dir, sev_desc),
    ]
    analysis_pool = [
        f"负载与 CPU 不匹配！load1={load1:.2f} 是 {cores} 核的 {load1/cores:.1f} 倍，但 CPU 使用率仅 {100-m['idle']:.1f}%，大量进程在等待 IO 或锁。",
        f"系统负载 {load1:.2f} 远超核心数 {cores}，但 CPU 空闲 {m['idle']:.1f}%，进程阻塞在 IO 或其他资源上。",
        f"负载异常：load1={load1:.2f}（基线 {bl_load:.2f}），CPU 空闲 {m['idle']:.1f}%，iowait={m['iowait']:.1f}%，进程排队严重。",
    ]
    recs = ["使用 ps aux 检查 D 状态进程", "排查 IO 等待和网络阻塞", "检查是否有锁竞争导致进程排队",
            "分析 NFS 或网络存储是否响应缓慢", "考虑增加 IO 带宽或优化存储", "检查是否有僵尸进程积累"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=time_range, metrics=metrics, baselines=baselines,
        baseline_desc=baseline_desc, findings=findings, severity=sev,
        status_emoji=emoji, status_text=sev_desc,
        analysis=rng.choice(analysis_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


ALL_GENERATORS = [
    gen_cpu_normal, gen_cpu_spike, gen_cpu_sustained_high,
    gen_cpu_iowait_high, gen_cpu_system_high, gen_cpu_load_mismatch,
]
