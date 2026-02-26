"""网络指标场景生成器。"""

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

MB = 1024 ** 2
GB = 1024 ** 3


def _net_metrics(rx_bps, tx_bps, rx_errs=0, tx_errs=0, rx_drops=0, tx_drops=0, device="eth0"):
    return [
        MetricSample("node_network_receive_bytes_total", {"device": device}, rx_bps, format_bytes(rx_bps) + "/s"),
        MetricSample("node_network_transmit_bytes_total", {"device": device}, tx_bps, format_bytes(tx_bps) + "/s"),
        MetricSample("node_network_receive_errs_total", {"device": device}, rx_errs, f"{rx_errs}"),
        MetricSample("node_network_transmit_errs_total", {"device": device}, tx_errs, f"{tx_errs}"),
        MetricSample("node_network_receive_drop_total", {"device": device}, rx_drops, f"{rx_drops}"),
        MetricSample("node_network_transmit_drop_total", {"device": device}, tx_drops, f"{tx_drops}"),
    ]


def gen_network_normal(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    bandwidth_mbps = rng.choice([100, 1000, 10000])
    rx_bps = rng.uniform(1, bandwidth_mbps * 0.3) * MB
    tx_bps = rng.uniform(1, bandwidth_mbps * 0.3) * MB
    metrics = _net_metrics(rx_bps, tx_bps)
    a_pool = [
        f"网络状态正常，接收 {format_bytes(rx_bps)}/s，发送 {format_bytes(tx_bps)}/s，带宽利用率低，无丢包错包。",
        f"网络健康，{bandwidth_mbps}Mbps 链路利用率正常，收发流量均衡，无异常。",
        f"网络运行平稳，流量在正常范围内，无错误和丢包。",
    ]
    recs = ["继续监控网络流量趋势", "保持当前网络配置", "定期检查网络设备状态"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "normal", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"net_rx_bps": rx_bps * rng.uniform(0.9, 1.1), "net_tx_bps": tx_bps * rng.uniform(0.9, 1.1)},
        baseline_desc=bd, findings=[], severity="normal",
        status_emoji="🟢", status_text="正常",
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(2, 3)),
    )


def gen_network_traffic_spike(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    bandwidth_mbps = rng.choice([100, 1000, 10000])
    rx_bps = rng.uniform(bandwidth_mbps * 0.6, bandwidth_mbps * 0.95) * MB
    tx_bps = rng.uniform(bandwidth_mbps * 0.3, bandwidth_mbps * 0.7) * MB
    bl_rx = rng.uniform(5, bandwidth_mbps * 0.2) * MB
    rx_drops = rng.randint(50, 5000)
    metrics = _net_metrics(rx_bps, tx_bps, rx_drops=rx_drops)
    dev, d = compute_deviation(rx_bps, bl_rx)
    sev, emoji, desc = severity_from_deviation(dev, "上升")
    finding = AnomalyFinding(
        "网络接收流量", rx_bps, format_bytes(rx_bps) + "/s",
        bl_rx, format_bytes(bl_rx) + "/s", dev, d, desc,
    )
    a_pool = [
        f"网络流量突增！接收 {format_bytes(rx_bps)}/s，远超基线 {format_bytes(bl_rx)}/s，丢包 {rx_drops}，带宽接近饱和。",
        f"入站流量激增至 {format_bytes(rx_bps)}/s，{bandwidth_mbps}Mbps 链路利用率过高，出现丢包。",
        f"网络流量异常，接收速率从基线 {format_bytes(bl_rx)}/s 飙升至 {format_bytes(rx_bps)}/s，需排查流量来源。",
    ]
    recs = ["使用 iftop/nethogs 排查高流量来源", "检查是否有 DDoS 攻击或异常访问",
            "评估是否需要限流或扩展带宽", "分析流量模式确认是否为正常业务高峰",
            "检查 CDN 或负载均衡配置"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"net_rx_bps": bl_rx}, baseline_desc=bd,
        findings=[finding], severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_network_asymmetric(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    # 收发严重不对称
    if rng.random() < 0.5:
        rx_bps = rng.uniform(200, 800) * MB
        tx_bps = rng.uniform(1, 10) * MB
        direction_desc = "接收远大于发送"
        ratio = rx_bps / tx_bps
    else:
        rx_bps = rng.uniform(1, 10) * MB
        tx_bps = rng.uniform(200, 800) * MB
        direction_desc = "发送远大于接收"
        ratio = tx_bps / rx_bps
    bl_ratio = rng.uniform(0.8, 1.5)
    dev, d = compute_deviation(ratio, bl_ratio)
    sev, emoji, desc = severity_from_deviation(dev, "上升")
    finding = AnomalyFinding(
        "收发比", ratio, f"{ratio:.1f}:1",
        bl_ratio, f"{bl_ratio:.1f}:1", dev, d, desc,
    )
    tx_errs = rng.randint(0, 100)
    metrics = _net_metrics(rx_bps, tx_bps, tx_errs=tx_errs)
    a_pool = [
        f"网络收发不对称，{direction_desc}，比值 {ratio:.1f}:1，可能存在数据泄露或异常传输。",
        f"流量不均衡告警：接收 {format_bytes(rx_bps)}/s，发送 {format_bytes(tx_bps)}/s，{direction_desc}。",
        f"网络流量异常不对称，收发比 {ratio:.1f}:1 远超正常范围，需排查原因。",
    ]
    recs = ["排查异常流量方向的进程和连接", "检查是否有数据备份或同步任务",
            "分析是否存在数据外泄风险", "检查网络设备是否有环路或配置错误",
            "审查防火墙规则和访问控制"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"net_ratio": bl_ratio}, baseline_desc=bd,
        findings=[finding], severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
    )


def gen_network_bandwidth_saturation(rng: random.Random, scenario_type_override: str | None = None) -> ScenarioConfig:
    instance = random_instance(rng)
    tr = random_time_range(rng)
    bd = random_baseline_desc(rng)
    bandwidth_mbps = rng.choice([100, 1000])
    max_bps = bandwidth_mbps * MB
    util_pct = rng.uniform(88, 99)
    total_bps = max_bps * util_pct / 100
    rx_bps = total_bps * rng.uniform(0.4, 0.6)
    tx_bps = total_bps - rx_bps
    bl_util = rng.uniform(20, 45)
    dev, d = compute_deviation(util_pct, bl_util)
    sev, emoji, desc = severity_from_deviation(dev, "上升")
    finding = AnomalyFinding(
        "带宽利用率", util_pct, format_percent(util_pct),
        bl_util, format_percent(bl_util), dev, d, desc,
    )
    rx_drops = rng.randint(100, 10000)
    tx_drops = rng.randint(50, 5000)
    metrics = _net_metrics(rx_bps, tx_bps, rx_drops=rx_drops, tx_drops=tx_drops)
    daily_growth = rng.uniform(1, 5)
    days = max(1, int((100 - util_pct) / daily_growth))
    cap = {"bandwidth": f"{bandwidth_mbps}Mbps", "current_util": format_percent(util_pct), "days_until_saturated": f"{days}"}
    a_pool = [
        f"带宽接近饱和！{bandwidth_mbps}Mbps 链路利用率 {util_pct:.1f}%，丢包严重（RX:{rx_drops} TX:{tx_drops}）。",
        f"网络带宽告警，利用率 {util_pct:.1f}% 远超基线 {bl_util:.1f}%，收发均接近上限，大量丢包。",
        f"带宽瓶颈：{bandwidth_mbps}Mbps 链路已用 {util_pct:.1f}%，约 {days} 天后完全饱和。",
    ]
    recs = ["评估带宽升级方案", "实施 QoS 流量优先级策略", "优化应用层数据传输效率",
            "考虑启用压缩减少传输量", "分析流量构成优化非关键传输",
            "部署 CDN 分流静态资源"]
    return ScenarioConfig(
        scenario_type=scenario_type_override or "single_anomaly", instance=instance,
        time_range=tr, metrics=metrics,
        baselines={"net_bandwidth_util": bl_util}, baseline_desc=bd,
        findings=[finding], severity=sev, status_emoji=emoji, status_text=desc,
        analysis=rng.choice(a_pool),
        recommendations=rng.sample(recs, k=rng.randint(3, 4)),
        capacity_info=cap,
    )


ALL_GENERATORS = [
    gen_network_normal, gen_network_traffic_spike,
    gen_network_asymmetric, gen_network_bandwidth_saturation,
]
