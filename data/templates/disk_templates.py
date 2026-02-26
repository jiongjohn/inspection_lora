"""磁盘指标场景生成器。"""

import random

from inspection_lora.data_utils import (
    AnomalyFinding,
    MetricSample,
    ScenarioConfig,
    compute_deviation,
    format_bytes,
    format_percent,
    random_baseline_desc,
    random_instance,
    random_time_range,
    severity_from_deviation,
)

GB = 1024 ** 3
TB = 1024 ** 4


def _disk_space(total_bytes, avail_bytes, device="/dev/sda1", mountpoint="/", fstype="ext4"):
    return [
        MetricSample("node_filesystem_size_bytes", {"device": device, "mountpoint": mountpoint, "fstype": fstype}, total_bytes, format_bytes(total_bytes)),
        MetricSample("node_filesystem_avail_bytes", {"device": device, "mountpoint": mountpoint, "fstype": fstype}, avail_bytes, format_bytes(avail_bytes)),
    ]


def _disk_io(read_bps, write_bps, io_util, device="sda"):
    return [
        MetricSample("node_disk_read_bytes_total", {"device": device}, read_bps, format_bytes(read_bps) + "/s"),
        MetricSample("node_disk_written_bytes_total", {"device": device}, write_bps, format_bytes(write_bps) + "/s"),
        MetricSample("node_disk_io_time_seconds_total", {"device": device}, io_util, format_percent(io_util)),
    ]


def _inode(total, free, device="/dev/sda1", mountpoint="/"):
    used_pct = (total - free) / total * 100 if total else 0
    return [
        MetricSample("node_filesystem_files", {"device": device, "mountpoint": mountpoint}, total, f"{total}"),
        MetricSample("node_filesystem_files_free", {"device": device, "mountpoint": mountpoint}, free, f"{free}"),
    ], used_pct


def gen_disk_normal(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    total_gb = rng.choice([100, 200, 500, 1000, 2000])
    total = total_gb * GB
    used_pct = rng.uniform(30, 60)
    avail = total * (1 - used_pct / 100)
    io_util = rng.uniform(5, 25)
    read_bps = rng.uniform(1, 30) * 1024 * 1024
    write_bps = rng.uniform(1, 20) * 1024 * 1024
    metrics = _disk_space(total, avail) + _disk_io(read_bps, write_bps, io_util)
    a_pool = [
        f"磁盘状态正常，总容量 {total_gb}GB，已用 {used_pct:.1f}%，剩余 {format_bytes(avail)}，IO 利用率 {io_util:.1f}%。",
        f"磁盘健康，空间充足（已用 {used_pct:.1f}%），IO 利用率 {io_util:.1f}%，读写正常。",
        f"磁盘运行平稳，{total_gb}GB 总容量使用 {used_pct:.1f}%，IO 无瓶颈。",
    ]
    recs = ["继续监控磁盘使用趋势", "保持当前存储配置", "定期清理临时文件"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "normal", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"disk_used_pct": used_pct * rng.uniform(0.95, 1.05)},
        baseline_desc=bd, findings=[], severity="normal",
        status_emoji="🟢", status_text="正常",
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(2, 3)),
    )


def gen_disk_space_low(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    total_gb = rng.choice([100, 200, 500, 1000])
    total = total_gb * GB
    used_pct = rng.uniform(88, 97)
    avail = total * (1 - used_pct / 100)
    bl_used = rng.uniform(50, 70)
    dev, d = compute_deviation(used_pct, bl_used)
    sev, emoji, desc = severity_from_deviation(dev, "上升")
    finding = AnomalyFinding(
        "磁盘使用率", used_pct, format_percent(used_pct),
        bl_used, format_percent(bl_used), dev, d, desc,
    )
    daily_gb = rng.uniform(0.5, 5.0)
    avail_gb = avail / GB
    days = max(1, int(avail_gb / daily_gb))
    cap = {"daily_growth": f"{daily_gb:.1f}GB", "days_until_full": f"{days}", "current_avail": format_bytes(avail)}
    a_pool = [
        f"磁盘空间告警！已用 {used_pct:.1f}%，仅剩 {format_bytes(avail)}，日增 {daily_gb:.1f}GB，约 {days} 天耗尽。",
        f"磁盘容量紧张，{total_gb}GB 总量已用 {used_pct:.1f}%，剩余 {format_bytes(avail)}，需尽快清理或扩容。",
        f"磁盘使用率 {used_pct:.1f}% 远超基线 {bl_used:.1f}%，可用空间不足 {format_bytes(avail)}。",
    ]
    recs = ["清理日志和临时文件释放空间", "排查大文件和异常增长目录", "评估磁盘扩容方案",
            "配置日志轮转策略", "迁移历史数据到归档存储"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=tr, metrics=_disk_space(total, avail),
        baselines={"disk_used_pct": bl_used}, baseline_desc=bd,
        findings=[finding], severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
        capacity_info=cap,
    )


def gen_disk_io_saturation(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    io_util = rng.uniform(85, 99)
    bl_io = rng.uniform(15, 35)
    read_bps = rng.uniform(50, 200) * 1024 * 1024
    write_bps = rng.uniform(30, 150) * 1024 * 1024
    dev, d = compute_deviation(io_util, bl_io)
    sev, emoji, desc = severity_from_deviation(dev, "上升")
    finding = AnomalyFinding(
        "磁盘 IO 利用率", io_util, format_percent(io_util),
        bl_io, format_percent(bl_io), dev, d, desc,
    )
    metrics = _disk_io(read_bps, write_bps, io_util)
    a_pool = [
        f"磁盘 IO 饱和！利用率 {io_util:.1f}%，读 {format_bytes(read_bps)}/s，写 {format_bytes(write_bps)}/s，严重影响性能。",
        f"IO，磁盘利用率 {io_util:.1f}% 远超基线 {bl_io:.1f}%，读写吞吐量接近上限。",
        f"磁盘 IO 接近满载（{io_util:.1f}%），大量请求排队，系统响应变慢。",
    ]
    recs = ["使用 iotop 排查高 IO 进程", "检查是否有大量随机 IO 操作", "评估升级到 SSD/NVMe",
            "优化数据库查询减少磁盘访问", "考虑增加 IO 调度优化", "检查 RAID 状态是否降级"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"disk_io_util": bl_io}, baseline_desc=bd,
        findings=[finding], severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_disk_inode_exhaustion(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    total_inodes = rng.choice([1_000_000, 5_000_000, 10_000_000, 50_000_000])
    used_pct = rng.uniform(92, 99.5)
    free_inodes = int(total_inodes * (1 - used_pct / 100))
    bl_used = rng.uniform(30, 60)
    dev, d = compute_deviation(used_pct, bl_used)
    sev, emoji, desc = severity_from_deviation(dev, "上升")
    finding = AnomalyFinding(
        "inode 使用率", used_pct, format_percent(used_pct),
        bl_used, format_percent(bl_used), dev, d, desc,
    )
    inode_metrics, _ = _inode(total_inodes, free_inodes)
    a_pool = [
        f"inode 即将耗尽！已用 {used_pct:.1f}%，仅剩 {free_inodes} 个 inode，无法创建新文件。",
        f"inode 使用率 {used_pct:.1f}% 远超基线 {bl_used:.1f}%，大量小文件占用 inode 资源。",
        f"inode 告警：总量 {total_inodes}，剩余 {free_inodes}，使用率 {used_pct:.1f}%，需立即处理。",
    ]
    recs = ["排查小文件密集目录（如 /tmp、缓存目录）", "清理过期的会话文件和临时文件",
            "检查是否有程序创建大量小文件", "考虑重新格式化分区增加 inode 数量",
            "迁移小文件到对象存储"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=tr, metrics=inode_metrics,
        baselines={"inode_used_pct": bl_used}, baseline_desc=bd,
        findings=[finding], severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_disk_write_latency(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    latency_ms = rng.uniform(50, 500)
    bl_latency = rng.uniform(2, 10)
    io_util = rng.uniform(70, 95)
    write_bps = rng.uniform(10, 80) * 1024 * 1024
    dev, d = compute_deviation(latency_ms, bl_latency)
    sev, emoji, desc = severity_from_deviation(dev, "上升")
    finding = AnomalyFinding(
        "磁盘写延迟", latency_ms, f"{latency_ms:.1f}ms",
        bl_latency, f"{bl_latency:.1f}ms", dev, d, desc,
    )
    metrics = [
        MetricSample("node_disk_write_time_seconds_total", {"device": "sda"}, latency_ms / 1000, f"{latency_ms:.1f}ms"),
        MetricSample("node_disk_io_time_seconds_total", {"device": "sda"}, io_util, format_percent(io_util)),
        MetricSample("node_disk_written_bytes_total", {"device": "sda"}, write_bps, format_bytes(write_bps) + "/s"),
    ]
    a_pool = [
        f"磁盘写延迟异常！当前 {latency_ms:.1f}ms，基线仅 {bl_latency:.1f}ms，IO 利用率 {io_util:.1f}%，写入性能严重下降。",
        f"写延迟飙升至 {latency_ms:.1f}ms（基线 {bl_latency:.1f}ms），磁盘 IO 利用率 {io_util:.1f}%，影响应用响应。",
        f"磁盘写性能劣化，延迟从 {bl_latency:.1f}ms 升至 {latency_ms:.1f}ms，吞吐 {format_bytes(write_bps)}。",
    ]
    recs = ["检查磁盘健康状态（SMART 信息）", "排查是否有大量同步写操作",
            "评估 IO 调度器配置是否合理", "检查文件系统是否需要 fsck",
            "考虑升级存储硬件或使用写缓存"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"disk_write_latency_ms": bl_latency}, baseline_desc=bd,
        findings=[finding], severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


ALL_GENERATORS = [
    gen_disk_normal, gen_disk_space_low, gen_disk_io_saturation,
    gen_disk_inode_exhaustion, gen_disk_write_latency,
]
