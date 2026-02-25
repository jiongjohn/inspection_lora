"""Prometheus 指标文本格式化与解析模块。"""

import re
from inspection_lora.data_utils import MetricSample


def _format_value(v: float) -> str:
    """格式化数值：整数不带小数点，否则保留1位。"""
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}"


def format_prometheus_line(sample: MetricSample) -> str:
    """格式化单条 Prometheus 指标行。"""
    val_str = _format_value(sample.value)
    if sample.labels:
        labels_str = ",".join(f'{k}="{v}"' for k, v in sample.labels.items())
        return f"{sample.name}{{{labels_str}}} {val_str}"
    return f"{sample.name} {val_str}"


def format_prometheus_block(samples: list[MetricSample]) -> str:
    """格式化多条指标，每行一条。"""
    return "\n".join(format_prometheus_line(s) for s in samples)


def format_baselines_block(baselines: dict[str, float], baseline_desc: str) -> str:
    """格式化历史基线块。"""
    lines = [f"历史基线({baseline_desc}):"]
    for key, val in baselines.items():
        lines.append(f"{key}: {_format_value(val)}")
    return "\n".join(lines)


def format_input_block(
    instance: str,
    time_range: tuple[str, str],
    samples: list[MetricSample],
    baselines: dict[str, float],
    baseline_desc: str,
) -> str:
    """组装完整的用户输入文本块。"""
    header = f"时间范围: {time_range[0]} - {time_range[1]}\n实例: {instance}"
    metrics_block = format_prometheus_block(samples)
    baselines_block = format_baselines_block(baselines, baseline_desc)
    return f"{header}\n\n{metrics_block}\n\n{baselines_block}"


_PROM_LINE_RE = re.compile(
    r"^([a-zA-Z_:][a-zA-Z0-9_:]*)"  # metric name
    r"(?:\{([^}]*)\})?"  # optional labels
    r"\s+"  # whitespace
    r"([0-9eE.+-]+)$"  # value
)


def parse_prometheus_line(line: str) -> MetricSample | None:
    """解析单条 Prometheus 指标行，返回 MetricSample 或 None。"""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    m = _PROM_LINE_RE.match(line)
    if not m:
        return None
    name = m.group(1)
    labels_str = m.group(2)
    value = float(m.group(3))
    labels: dict[str, str] = {}
    if labels_str:
        for pair in labels_str.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                labels[k.strip()] = v.strip().strip('"')
    return MetricSample(name=name, labels=labels, value=value, display_value=str(value))


def parse_prometheus_block(text: str) -> list[MetricSample]:
    """解析多行 Prometheus 文本。"""
    results = []
    for line in text.strip().split("\n"):
        sample = parse_prometheus_line(line)
        if sample is not None:
            results.append(sample)
    return results
