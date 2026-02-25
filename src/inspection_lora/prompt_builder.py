"""ScenarioConfig 转换为 mlx-lm chat messages 格式。

纯格式化模块，不做任何数学计算。所有数值均来自 ScenarioConfig 预计算。
"""

from inspection_lora.data_utils import ScenarioConfig, SYSTEM_PROMPT
from inspection_lora.metrics_parser import format_input_block


def build_user_prompt(config: ScenarioConfig) -> str:
    """构建用户输入文本。"""
    text = format_input_block(
        config.instance,
        config.time_range,
        config.metrics,
        config.baselines,
        config.baseline_desc,
    )
    if config.scenario_type == "capacity" and config.capacity_info:
        parts = ["\n趋势数据:"]
        for k, v in config.capacity_info.items():
            parts.append(f"{k}: {v}")
        text += "\n".join(parts)
    return text


def _format_findings(findings) -> str:
    """格式化异常发现列表。"""
    lines = []
    for i, f in enumerate(findings, 1):
        lines.append(
            f"{i}. {f.metric_name} 当前值 {f.current_display}，"
            f"较基线 {f.baseline_display} {f.direction} {f.deviation_percent:.1f}%，"
            f"{f.severity_desc}"
        )
    return "\n".join(lines)


def _format_recommendations(recs: list[str]) -> str:
    """格式化建议列表。"""
    return "\n".join(f"{i}. {r}" for i, r in enumerate(recs, 1))


def build_assistant_response(config: ScenarioConfig) -> str:
    """根据 scenario_type 构建助手回复文本。"""
    t = config.scenario_type

    if t == "single_anomaly":
        return _build_single_anomaly(config)
    elif t == "multi_metric":
        return _build_multi_metric(config)
    elif t == "normal":
        return _build_normal(config)
    elif t == "capacity":
        return _build_capacity(config)
    elif t == "health":
        return _build_health(config)
    elif t == "report":
        return _build_report(config)
    else:
        return _build_single_anomaly(config)


def _build_single_anomaly(c: ScenarioConfig) -> str:
    parts = [
        f"## 巡检结果: {c.status_emoji} {c.status_text}",
        "",
        "**异常发现:**",
        _format_findings(c.findings),
        "",
        f"**综合判断:** {c.analysis}",
        "",
        "**建议:**",
        _format_recommendations(c.recommendations),
    ]
    return "\n".join(parts)


def _build_multi_metric(c: ScenarioConfig) -> str:
    parts = [
        f"## 巡检结果: {c.status_emoji} {c.status_text}",
        "",
        "**异常发现:**",
        _format_findings(c.findings),
        "",
        f"**关联分析:** {c.analysis}",
        "",
        "**建议:**",
        _format_recommendations(c.recommendations),
    ]
    return "\n".join(parts)


def _build_normal(c: ScenarioConfig) -> str:
    metric_lines = []
    for i, m in enumerate(c.metrics, 1):
        metric_lines.append(f"{i}. {m.name} 当前值 {m.display_value}，基线内，状态正常")
    recs = ["1. 继续保持当前监控策略"]
    for i, r in enumerate(c.recommendations, 2):
        recs.append(f"{i}. {r}")
    parts = [
        "## 巡检结果: 🟢 正常",
        "",
        "**指标概览:**",
        "\n".join(metric_lines),
        "",
        f"**综合判断:** {c.analysis}",
        "",
        "**建议:**",
        "\n".join(recs),
    ]
    return "\n".join(parts)


def _build_capacity(c: ScenarioConfig) -> str:
    cap_lines = []
    if c.capacity_info:
        for k, v in c.capacity_info.items():
            cap_lines.append(f"- {k}: {v}")
    if c.findings:
        cap_lines.append("")
        cap_lines.append(_format_findings(c.findings))
    parts = [
        f"## 巡检结果: {c.status_emoji} 容量预警",
        "",
        "**容量分析:**",
        "\n".join(cap_lines) if cap_lines else "暂无趋势数据",
        "",
        f"**综合判断:** {c.analysis}",
        "",
        "**建议:**",
        _format_recommendations(c.recommendations),
    ]
    return "\n".join(parts)


def _build_health(c: ScenarioConfig) -> str:
    score = c.health_score if c.health_score is not None else 0
    metric_lines = []
    finding_names = {f.metric_name for f in c.findings}
    for i, m in enumerate(c.metrics, 1):
        matched = None
        for f in c.findings:
            if f.metric_name in m.name or m.name in f.metric_name:
                matched = f
                break
        if matched:
            metric_lines.append(f"{i}. {m.name}: {m.display_value} - {matched.severity_desc}")
        else:
            metric_lines.append(f"{i}. {m.name}: {m.display_value} - 正常")
    parts = [
        f"## 巡检结果: {c.status_emoji} 健康评分 {score}/100",
        "",
        "**各项指标:**",
        "\n".join(metric_lines),
        "",
        f"**综合判断:** {c.analysis}",
        "",
        "**建议:**",
        _format_recommendations(c.recommendations),
    ]
    return "\n".join(parts)


def _build_report(c: ScenarioConfig) -> str:
    score = c.health_score if c.health_score is not None else 0
    if c.findings:
        detail_lines = _format_findings(c.findings)
    else:
        detail_lines = "\n".join(
            f"{i}. {m.name}: {m.display_value} - 正常"
            for i, m in enumerate(c.metrics, 1)
        )
    parts = [
        "## 巡检报告",
        "",
        f"**概览:** {c.status_emoji} {c.status_text}",
        f"**健康评分:** {score}/100",
        f"**巡检时间:** {c.time_range[0]} - {c.time_range[1]}",
        f"**巡检实例:** {c.instance}",
        "",
        "### 指标详情",
        detail_lines,
        "",
        "### 综合判断",
        c.analysis,
        "",
        "### 建议措施",
        _format_recommendations(c.recommendations),
    ]
    return "\n".join(parts)


def build_chat_messages(config: ScenarioConfig) -> dict:
    """构建 mlx-lm chat messages 格式。"""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(config)},
            {"role": "assistant", "content": build_assistant_response(config)},
        ]
    }
