"""多指标组合场景生成器。

生成涉及多个指标类别关联异常的复合场景。
"""

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
MB = 1024 ** 2


def gen_cpu_io_correlation(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    """CPU iowait 高 + 磁盘 IO 饱和关联场景。"""
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    cores = rng.choice([4, 8, 16, 32])
    iowait = rng.uniform(30, 60)
    idle = rng.uniform(5, 20)
    user = rng.uniform(10, 30)
    system = rng.uniform(5, 15)
    io_util = rng.uniform(85, 99)
    bl_iowait = rng.uniform(1, 5)
    bl_io = rng.uniform(15, 30)
    load1 = rng.uniform(cores * 2, cores * 5)

    iw_dev, iw_d = compute_deviation(iowait, bl_iowait)
    io_dev, io_d = compute_deviation(io_util, bl_io)
    max_dev = max(iw_dev, io_dev)
    sev, emoji, desc = severity_from_deviation(max_dev, "上升")

    findings = [
        AnomalyFinding("CPU IO 等待", iowait, format_percent(iowait), bl_iowait, format_percent(bl_iowait), iw_dev, iw_d, desc),
        AnomalyFinding("磁盘 IO 利用率", io_util, format_percent(io_util), bl_io, format_percent(bl_io), io_dev, io_d, desc),
    ]
    metrics = [
        MetricSample("node_cpu_seconds_total", {"cpu": "0", "mode": "iowait"}, iowait, format_percent(iowait)),
        MetricSample("node_cpu_seconds_total", {"cpu": "0", "mode": "idle"}, idle, format_percent(idle)),
        MetricSample("node_cpu_seconds_total", {"cpu": "0", "mode": "user"}, user, format_percent(user)),
        MetricSample("node_disk_io_time_seconds_total", {"device": "sda"}, io_util, format_percent(io_util)),
        MetricSample("node_load1", {}, load1, f"{load1:.2f}"),
    ]
    a_pool = [
        f"CPU iowait {iowait:.1f}% 与磁盘 IO 利用率 {io_util:.1f}% 强关联，磁盘瓶颈导致 CPU 等待，负载 {load1:.2f}。",
        f"磁盘 IO 饱和（{io_util:.1f}%）引发 CPU iowait 飙升至 {iowait:.1f}%，进程大量阻塞在 IO 上。",
        f"IO 关联异常：磁盘利用率 {io_util:.1f}% 导致 CPU iowait {iowait:.1f}%，系统负载 {load1:.2f} 远超 {cores} 核。",
    ]
    recs = ["优先解决磁盘 IO 瓶颈", "使用 iotop 定位高 IO 进程", "评估升级存储到 SSD/NVMe",
            "优化应用 IO 模式（批量写、异步 IO）", "检查是否有全表扫描或大量日志写入"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "multi_metric", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"cpu_iowait": bl_iowait, "disk_io_util": bl_io}, baseline_desc=bd,
        findings=findings, severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_memory_swap_cascade(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    """内存不足 + swap 活跃 + 磁盘 IO 升高级联场景。"""
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    tgb = rng.choice([8, 16, 32, 64])
    total = tgb * GB
    mem_pct = rng.uniform(3, 10)
    avail = total * mem_pct / 100
    bl_mem = rng.uniform(40, 60)
    io_util = rng.uniform(60, 90)
    bl_io = rng.uniform(10, 25)

    m_dev, m_d = compute_deviation(mem_pct, bl_mem)
    io_dev, io_d = compute_deviation(io_util, bl_io)
    max_dev = max(m_dev, io_dev)
    sev, emoji, desc = severity_from_deviation(max_dev, "下降")

    findings = [
        AnomalyFinding("内存可用率", mem_pct, format_percent(mem_pct), bl_mem, format_percent(bl_mem), m_dev, m_d, desc),
        AnomalyFinding("磁盘 IO 利用率", io_util, format_percent(io_util), bl_io, format_percent(bl_io), io_dev, io_d, "上升"),
    ]
    metrics = [
        MetricSample("node_memory_MemTotal_bytes", {}, total, format_bytes(total)),
        MetricSample("node_memory_MemAvailable_bytes", {}, avail, format_bytes(avail)),
        MetricSample("node_disk_io_time_seconds_total", {"device": "sda"}, io_util, format_percent(io_util)),
    ]
    a_pool = [
        f"内存-swap 级联异常：可用内存仅 {mem_pct:.1f}%（{format_bytes(avail)}），swap 活跃导致磁盘 IO 升至 {io_util:.1f}%。",
        f"内存不足触发 swap，可用 {mem_pct:.1f}%，磁盘 IO {io_util:.1f}% 因页面交换大幅上升，系统性能严重下降。",
        f"级联告警：内存 {mem_pct:.1f}% → swap 活跃 → 磁盘 IO {io_util:.1f}%，形成恶性循环。",
    ]
    recs = ["优先释放内存或重启高内存进程", "增加物理内存", "调整 swappiness 参数",
            "排查内存泄漏", "配置 OOM killer 优先级保护关键服务"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "multi_metric", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"mem_avail_pct": bl_mem, "disk_io_util": bl_io}, baseline_desc=bd,
        findings=findings, severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_cpu_memory_load(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    """CPU 高 + 内存高双重压力场景。"""
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    cores = rng.choice([4, 8, 16, 32])
    cpu_user = rng.uniform(70, 92)
    bl_cpu = rng.uniform(20, 35)
    tgb = rng.choice([8, 16, 32, 64])
    total = tgb * GB
    mem_pct = rng.uniform(5, 15)
    avail = total * mem_pct / 100
    bl_mem = rng.uniform(40, 60)
    load1 = rng.uniform(cores * 2, cores * 4)

    c_dev, c_d = compute_deviation(cpu_user, bl_cpu)
    m_dev, m_d = compute_deviation(mem_pct, bl_mem)
    max_dev = max(c_dev, m_dev)
    sev, emoji, desc = severity_from_deviation(max_dev, "上升")

    findings = [
        AnomalyFinding("CPU 用户态", cpu_user, format_percent(cpu_user), bl_cpu, format_percent(bl_cpu), c_dev, c_d, desc),
        AnomalyFinding("内存可用率", mem_pct, format_percent(mem_pct), bl_mem, format_percent(bl_mem), m_dev, m_d, "下降"),
    ]
    metrics = [
        MetricSample("node_cpu_seconds_total", {"cpu": "0", "mode": "user"}, cpu_user, format_percent(cpu_user)),
        MetricSample("node_memory_MemTotal_bytes", {}, total, format_bytes(total)),
        MetricSample("node_memory_MemAvailable_bytes", {}, avail, format_bytes(avail)),
        MetricSample("node_load1", {}, load1, f"{load1:.2f}"),
    ]
    a_pool = [
        f"CPU 和内存双重压力！CPU 用户态 {cpu_user:.1f}%，内存可用仅 {mem_pct:.1f}%（{format_bytes(avail)}），负载 {load1:.2f}。",
        f"系统资源全面紧张，CPU {cpu_user:.1f}% 接近满载，内存 {mem_pct:.1f}% 告急，{cores} 核负载 {load1:.2f}。",
        f"双重异常：CPU 从基线 {bl_cpu:.1f}% 升至 {cpu_user:.1f}%，内存从 {bl_mem:.1f}% 降至 {mem_pct:.1f}%，需紧急处理。",
    ]
    recs = ["排查资源消耗最高的进程", "评估是否需要紧急扩容", "检查是否有异常任务或攻击",
            "优化应用资源使用效率", "考虑水平扩展分散负载", "启用资源限制（cgroup）防止单进程耗尽资源"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "multi_metric", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"cpu_user": bl_cpu, "mem_avail_pct": bl_mem}, baseline_desc=bd,
        findings=findings, severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 5)),
    )


def gen_disk_network_backup(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    """磁盘 IO 高 + 网络流量高（备份/同步场景）。"""
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    io_util = rng.uniform(75, 98)
    bl_io = rng.uniform(15, 30)
    tx_bps = rng.uniform(100, 500) * MB
    bl_tx = rng.uniform(5, 30) * MB

    io_dev, io_d = compute_deviation(io_util, bl_io)
    tx_dev, tx_d = compute_deviation(tx_bps, bl_tx)
    max_dev = max(io_dev, tx_dev)
    sev, emoji, desc = severity_from_deviation(max_dev, "上升")

    findings = [
        AnomalyFinding("磁盘 IO 利用率", io_util, format_percent(io_util), bl_io, format_percent(bl_io), io_dev, io_d, desc),
        AnomalyFinding("网络发送流量", tx_bps, format_bytes(tx_bps) + "/s", bl_tx, format_bytes(bl_tx) + "/s", tx_dev, tx_d, desc),
    ]
    read_bps = rng.uniform(50, 200) * MB
    metrics = [
        MetricSample("node_disk_io_time_seconds_total", {"device": "sda"}, io_util, format_percent(io_util)),
        MetricSample("node_disk_read_bytes_total", {"device": "sda"}, read_bps, format_bytes(read_bps) + "/s"),
        MetricSample("node_network_transmit_bytes_total", {"device": "eth0"}, tx_bps, format_bytes(tx_bps) + "/s"),
    ]
    a_pool = [
        f"磁盘 IO（{io_util:.1f}%）和网络发送（{format_bytes(tx_bps)}/s）同时飙高，疑似备份或数据同步任务。",
        f"磁盘读取密集 + 网络发送激增，IO {io_util:.1f}%，TX {format_bytes(tx_bps)}/s，典型的数据传输模式。",
        f"关联异常：磁盘 IO {io_util:.1f}% 与网络 TX {format_bytes(tx_bps)}/s 同步升高，检查备份/复制任务。",
    ]
    recs = ["检查是否有备份或数据同步任务在运行", "调整备份窗口避开业务高峰",
            "优化备份策略（增量备份替代全量）", "限制备份任务的 IO 和带宽",
            "考虑使用专用备份网络"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "multi_metric", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"disk_io_util": bl_io, "net_tx_bps": bl_tx}, baseline_desc=bd,
        findings=findings, severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_full_stack_degradation(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    """CPU + 内存 + 磁盘 + 网络全面劣化场景。"""
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    cores = rng.choice([4, 8, 16, 32])
    cpu_user = rng.uniform(60, 85)
    bl_cpu = rng.uniform(20, 35)
    tgb = rng.choice([16, 32, 64])
    total = tgb * GB
    mem_pct = rng.uniform(5, 15)
    avail = total * mem_pct / 100
    bl_mem = rng.uniform(40, 60)
    io_util = rng.uniform(70, 95)
    bl_io = rng.uniform(15, 30)
    rx_bps = rng.uniform(50, 300) * MB
    bl_rx = rng.uniform(5, 30) * MB
    load1 = rng.uniform(cores * 2, cores * 5)

    c_dev, c_d = compute_deviation(cpu_user, bl_cpu)
    m_dev, m_d = compute_deviation(mem_pct, bl_mem)
    io_dev, io_d = compute_deviation(io_util, bl_io)
    n_dev, n_d = compute_deviation(rx_bps, bl_rx)
    max_dev = max(c_dev, m_dev, io_dev, n_dev)
    sev, emoji, desc = severity_from_deviation(max_dev, "上升")

    findings = [
        AnomalyFinding("CPU 用户态", cpu_user, format_percent(cpu_user), bl_cpu, format_percent(bl_cpu), c_dev, c_d, desc),
        AnomalyFinding("内存可用率", mem_pct, format_percent(mem_pct), bl_mem, format_percent(bl_mem), m_dev, m_d, "下降"),
        AnomalyFinding("磁盘 IO 利用率", io_util, format_percent(io_util), bl_io, format_percent(bl_io), io_dev, io_d, desc),
        AnomalyFinding("网络接收流量", rx_bps, format_bytes(rx_bps) + "/s", bl_rx, format_bytes(bl_rx) + "/s", n_dev, n_d, desc),
    ]
    metrics = [
        MetricSample("node_cpu_seconds_total", {"cpu": "0", "mode": "user"}, cpu_user, format_percent(cpu_user)),
        MetricSample("node_memory_MemTotal_bytes", {}, total, format_bytes(total)),
        MetricSample("node_memory_MemAvailable_bytes", {}, avail, format_bytes(avail)),
        MetricSample("node_disk_io_time_seconds_total", {"device": "sda"}, io_util, format_percent(io_util)),
        MetricSample("node_network_receive_bytes_total", {"device": "eth0"}, rx_bps, format_bytes(rx_bps) + "/s"),
        MetricSample("node_load1", {}, load1, f"{load1:.2f}"),
    ]
    a_pool = [
        f"全面劣化！CPU {cpu_user:.1f}%，内存 {mem_pct:.1f}%，磁盘 IO {io_util:.1f}%，网络 {format_bytes(rx_bps)}/s，系统濒临崩溃。",
        f"多维度异常：CPU/内存/磁盘/网络全面告警，负载 {load1:.2f}，系统处于严重过载状态。",
        f"系统全面过载，所有核心指标均超出基线，CPU {cpu_user:.1f}%、内存 {mem_pct:.1f}%、IO {io_util:.1f}%，需立即干预。",
    ]
    recs = ["立即启动应急响应流程", "排查是否遭受攻击或异常流量", "考虑紧急扩容或流量切换",
            "逐一排查各维度异常根因", "启用限流保护核心服务", "准备回滚方案"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "multi_metric", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"cpu_user": bl_cpu, "mem_avail_pct": bl_mem, "disk_io_util": bl_io, "net_rx_bps": bl_rx},
        baseline_desc=bd, findings=findings, severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(4, 5)),
    )


def gen_load_cpu_divergence(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    """负载高但 CPU 使用率不高（IO/锁等待）场景。"""
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    cores = rng.choice([4, 8, 16, 32])
    cpu_user = rng.uniform(15, 35)
    idle = rng.uniform(30, 50)
    iowait = rng.uniform(10, 30)
    load1 = rng.uniform(cores * 3, cores * 8)
    bl_load = rng.uniform(0.5, cores * 1.5)

    l_dev, l_d = compute_deviation(load1, bl_load)
    sev, emoji, desc = severity_from_deviation(l_dev, "上升")

    findings = [
        AnomalyFinding("1 分钟负载", load1, f"{load1:.2f}", bl_load, f"{bl_load:.2f}", l_dev, l_d, desc),
    ]
    metrics = [
        MetricSample("node_cpu_seconds_total", {"cpu": "0", "mode": "user"}, cpu_user, format_percent(cpu_user)),
        MetricSample("node_cpu_seconds_total", {"cpu": "0", "mode": "idle"}, idle, format_percent(idle)),
        MetricSample("node_cpu_seconds_total", {"cpu": "0", "mode": "iowait"}, iowait, format_percent(iowait)),
        MetricSample("node_load1", {}, load1, f"{load1:.2f}"),
    ]
    a_pool = [
        f"负载与 CPU 背离！load1={load1:.2f}（{cores} 核的 {load1/cores:.1f} 倍），但 CPU 空闲 {idle:.1f}%，iowait {iowait:.1f}%，进程阻塞在 IO/锁上。",
        f"系统负载 {load1:.2f} 异常高，但 CPU 使用率仅 {cpu_user:.1f}%，大量进程处于不可中断等待状态。",
        f"负载-CPU 背离：load {load1:.2f} 远超 {cores} 核，CPU 空闲 {idle:.1f}%，iowait {iowait:.1f}%，瓶颈在 IO 或锁。",
    ]
    recs = ["使用 ps aux 检查 D 状态进程", "排查 IO 等待和 NFS 挂载问题",
            "检查数据库锁竞争", "分析是否有网络存储响应缓慢",
            "考虑优化 IO 密集型操作"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "multi_metric", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"load1": bl_load}, baseline_desc=bd,
        findings=findings, severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


ALL_GENERATORS = [
    gen_cpu_io_correlation, gen_memory_swap_cascade, gen_cpu_memory_load,
    gen_disk_network_backup, gen_full_stack_degradation, gen_load_cpu_divergence,
]
