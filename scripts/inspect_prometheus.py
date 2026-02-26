#!/usr/bin/env python3
"""
Prometheus 巡检分析 CLI

通过 MCP 连接 Prometheus 获取指标数据，调用微调模型进行智能巡检分析。

用法:
    # 基本用法（分析所有 node_exporter 实例）
    python scripts/inspect_prometheus.py

    # 指定实例和时间范围
    python scripts/inspect_prometheus.py --instance "node-web-01:9100" --range 2h

    # 指定 MCP 和模型服务地址
    python scripts/inspect_prometheus.py \
        --mcp-url http://localhost:11909/sse \
        --llm-url http://localhost:8080/v1 \
        --instance "node-web-01:9100"

前置条件:
    1. Prometheus MCP Server 已启动 (SSE 传输)
    2. mlx_lm server 已启动:
       python -m mlx_lm server --model Qwen/Qwen2.5-1.5B-Instruct \
           --adapter-path outputs/adapters --port 8080
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import OpenAI


# ── 系统提示词（与训练数据一致）──────────────────────────────
SYSTEM_PROMPT = (
    "你是一个专业的基础设施监控助手,负责分析 Prometheus 指标数据并提供巡检报告。"
    "请根据提供的指标数据进行分析,识别异常,给出判断和建议。"
)

# ── 要采集的 node_exporter 指标 ──────────────────────────────
NODE_METRICS = {
    "cpu": [
        'avg(rate(node_cpu_seconds_total{mode="user",instance="__INST__"}[5m])) * 100',
        'avg(rate(node_cpu_seconds_total{mode="system",instance="__INST__"}[5m])) * 100',
        'avg(rate(node_cpu_seconds_total{mode="idle",instance="__INST__"}[5m])) * 100',
        'avg(rate(node_cpu_seconds_total{mode="iowait",instance="__INST__"}[5m])) * 100',
    ],
    "memory": [
        'node_memory_MemTotal_bytes{instance="__INST__"}',
        'node_memory_MemAvailable_bytes{instance="__INST__"}',
        'node_memory_Buffers_bytes{instance="__INST__"}',
        'node_memory_Cached_bytes{instance="__INST__"}',
    ],
    "disk": [
        'node_filesystem_size_bytes{instance="__INST__",mountpoint="/"}',
        'node_filesystem_avail_bytes{instance="__INST__",mountpoint="/"}',
        'rate(node_disk_read_bytes_total{instance="__INST__"}[5m])',
        'rate(node_disk_written_bytes_total{instance="__INST__"}[5m])',
    ],
    "network": [
        'rate(node_network_receive_bytes_total{instance="__INST__",device!="lo"}[5m])',
        'rate(node_network_transmit_bytes_total{instance="__INST__",device!="lo"}[5m])',
    ],
    "load": [
        'node_load1{instance="__INST__"}',
        'node_load5{instance="__INST__"}',
        'node_load15{instance="__INST__"}',
    ],
}

# ── 基线查询（过去 7 天平均）────────────────────────────────
BASELINE_METRICS = {
    "cpu_user_avg": 'avg(avg_over_time(rate(node_cpu_seconds_total{mode="user",instance="__INST__"}[5m])[7d:])) * 100',
    "cpu_system_avg": 'avg(avg_over_time(rate(node_cpu_seconds_total{mode="system",instance="__INST__"}[5m])[7d:])) * 100',
    "mem_available_avg": 'avg_over_time(node_memory_MemAvailable_bytes{instance="__INST__"}[7d])',
    "disk_avail_avg": 'avg_over_time(node_filesystem_avail_bytes{instance="__INST__",mountpoint="/"}[7d])',
    "load1_avg": 'avg_over_time(node_load1{instance="__INST__"}[7d])',
}


def format_bytes(value: float) -> str:
    """字节数格式化"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(value) < 1024:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} PB"


def format_value(metric_name: str, value: float) -> str:
    """根据指标名称格式化数值"""
    if "bytes" in metric_name.lower():
        return format_bytes(value)
    elif (
        "cpu" in metric_name.lower()
        or "idle" in metric_name.lower()
        or "iowait" in metric_name.lower()
    ):
        return f"{value:.2f}%"
    else:
        return f"{value:.4f}"


async def get_instances(session: ClientSession) -> list[str]:
    """获取所有 node_exporter 实例"""
    result = await session.call_tool("execute_query", {"query": "up{job=~'node.*'}"})
    text = result.content[0].text
    data = json.loads(text)

    instances = []
    if isinstance(data, list):
        for item in data:
            inst = item.get("metric", {}).get("instance", "")
            if inst:
                instances.append(inst)
    elif isinstance(data, dict) and "result" in data.get("data", {}):
        for item in data["data"]["result"]:
            inst = item.get("metric", {}).get("instance", "")
            if inst:
                instances.append(inst)

    return sorted(set(instances))


async def query_metric(session: ClientSession, query: str) -> list[dict]:
    """执行单个 PromQL 查询"""
    try:
        result = await session.call_tool("execute_query", {"query": query})
        text = result.content[0].text
        data = json.loads(text)

        # 兼容不同返回格式
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get("data", {}).get("result", [])
        return []
    except Exception as e:
        print(f"  ⚠️  查询失败: {query[:60]}... → {e}", file=sys.stderr)
        return []


async def collect_metrics(session: ClientSession, instance: str) -> dict:
    """采集指定实例的所有指标"""
    results = {"current": {}, "baseline": {}}

    # 采集当前指标
    for category, queries in NODE_METRICS.items():
        results["current"][category] = []
        for query_tpl in queries:
            query = query_tpl.replace("__INST__", instance)
            data = await query_metric(session, query)
            for item in data:
                value = float(item.get("value", [0, "0"])[1]) if "value" in item else 0
                results["current"][category].append(
                    {
                        "query": query_tpl.split("{")[0].split("(")[-1]
                        if "(" in query_tpl
                        else query_tpl.split("{")[0],
                        "labels": item.get("metric", {}),
                        "value": value,
                    }
                )

    # 采集基线
    for name, query_tpl in BASELINE_METRICS.items():
        query = query_tpl.replace("__INST__", instance)
        data = await query_metric(session, query)
        if data:
            value = float(data[0].get("value", [0, "0"])[1])
            results["baseline"][name] = value

    return results


def build_prompt(instance: str, metrics: dict, time_range: str) -> str:
    """将采集到的指标构建为模型输入格式"""
    now = datetime.now(timezone.utc)
    lines = []
    lines.append(
        f"时间范围: {(now - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')} - {now.strftime('%Y-%m-%d %H:%M')}"
    )
    lines.append(f"实例: {instance}")
    lines.append("")

    # 当前指标
    for category, items in metrics["current"].items():
        if not items:
            continue
        lines.append(f"# {category.upper()}")
        for item in items:
            metric_name = item["query"]
            value = item["value"]
            formatted = format_value(metric_name, value)
            labels = item.get("labels", {})
            label_str = ""
            if labels:
                filtered = {
                    k: v for k, v in labels.items() if k not in ("__name__", "instance", "job")
                }
                if filtered:
                    label_str = "{" + ",".join(f'{k}="{v}"' for k, v in filtered.items()) + "}"
            lines.append(f"{metric_name}{label_str} {formatted}")
        lines.append("")

    # 基线数据
    if metrics["baseline"]:
        lines.append("基线数据 (过去7天平均):")
        for name, value in metrics["baseline"].items():
            if "bytes" in name.lower() or "mem" in name.lower() or "disk" in name.lower():
                lines.append(f"  {name}: {format_bytes(value)}")
            elif "cpu" in name.lower():
                lines.append(f"  {name}: {value:.2f}%")
            else:
                lines.append(f"  {name}: {value:.4f}")

    return "\n".join(lines)


def call_llm(llm_url: str, prompt: str, model: str = "default") -> str:
    """调用微调模型进行分析"""
    client = OpenAI(base_url=llm_url, api_key="none")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=1024,
    )

    return response.choices[0].message.content


async def inspect_instance(
    session: ClientSession,
    instance: str,
    llm_url: str,
    time_range: str,
) -> dict:
    """对单个实例执行完整巡检"""
    print(f"\n{'=' * 60}")
    print(f"🔍 巡检实例: {instance}")
    print(f"{'=' * 60}")

    # 1. 采集指标
    print("  📊 采集指标数据...")
    metrics = await collect_metrics(session, instance)

    current_count = sum(len(v) for v in metrics["current"].values())
    baseline_count = len(metrics["baseline"])
    print(f"  ✅ 采集完成: {current_count} 个当前指标, {baseline_count} 个基线指标")

    # 2. 构建 prompt
    prompt = build_prompt(instance, metrics, time_range)

    # 3. 调用模型分析
    print("  🤖 模型分析中...")
    try:
        analysis = call_llm(llm_url, prompt)
    except Exception as e:
        analysis = f"❌ 模型调用失败: {e}"
        print(f"  {analysis}", file=sys.stderr)

    # 4. 输出结果
    print(f"\n{analysis}")

    return {
        "instance": instance,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics_collected": current_count,
        "baseline_collected": baseline_count,
        "prompt": prompt,
        "analysis": analysis,
    }


async def run(args: argparse.Namespace):
    """主运行逻辑"""
    print(f"🔗 连接 Prometheus MCP: {args.mcp_url}")
    print(f"🤖 模型服务: {args.llm_url}")

    async with sse_client(args.mcp_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 健康检查
            try:
                health = await session.call_tool("health_check", {})
                print(f"✅ MCP 连接成功: {health.content[0].text[:100]}")
            except Exception as e:
                print(f"⚠️  健康检查失败 (继续执行): {e}", file=sys.stderr)

            # 确定要巡检的实例
            if args.instance:
                instances = [args.instance]
            else:
                print("\n📋 获取实例列表...")
                instances = await get_instances(session)
                if not instances:
                    print("❌ 未发现 node_exporter 实例", file=sys.stderr)
                    sys.exit(1)
                print(f"  发现 {len(instances)} 个实例: {', '.join(instances)}")

            # 逐个巡检
            results = []
            for inst in instances:
                result = await inspect_instance(session, inst, args.llm_url, args.range)
                results.append(result)

            # 保存结果
            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"\n📄 结果已保存至: {output_path}")

            # 汇总
            print(f"\n{'=' * 60}")
            print(f"📊 巡检完成: 共 {len(results)} 个实例")
            print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(
        description="Prometheus 巡检分析 — 通过 MCP 获取指标，调用微调模型分析"
    )
    parser.add_argument(
        "--mcp-url",
        default="http://localhost:11909/sse",
        help="Prometheus MCP Server SSE 地址 (default: http://localhost:11909/sse)",
    )
    parser.add_argument(
        "--llm-url",
        default="http://localhost:8080/v1",
        help="微调模型 API 地址 (default: http://localhost:8080/v1)",
    )
    parser.add_argument(
        "--instance",
        default=None,
        help="指定巡检实例 (如 node-web-01:9100)，不指定则巡检所有实例",
    )
    parser.add_argument(
        "--range",
        default="1h",
        help="分析时间范围 (default: 1h)",
    )
    parser.add_argument(
        "--output",
        default="outputs/inspection_report.json",
        help="结果输出路径 (default: outputs/inspection_report.json)",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
