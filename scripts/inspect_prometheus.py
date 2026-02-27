#!/usr/bin/env python3
"""
Prometheus 巡检脚本

直接查询 Prometheus HTTP API 收集指标数据，然后调用本地 LLM (OpenAI 兼容 API) 进行巡检分析。

功能:
1. 查询 Prometheus HTTP API (无 MCP 依赖)
2. 自动发现 node_exporter 实例或接受指定实例
3. 收集 CPU、内存、磁盘、网络、负载指标 + 7天基线
4. 格式化数据为模型期望的输入格式
5. 调用本地 mlx_lm 服务器 (OpenAI 兼容) 进行分析
6. 打印巡检报告并保存 JSON

使用示例:
    python scripts/inspect_prometheus.py --prometheus-url http://172.16.12.114:31909
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional


def prom_query(base_url: str, promql: str) -> List[Dict[str, Any]]:
    """查询 Prometheus instant query API"""
    url = base_url.rstrip("/") + "/api/v1/query"
    params = urllib.parse.urlencode({"query": promql})
    full_url = url + "?" + params

    try:
        with urllib.request.urlopen(full_url, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") == "success":
                return data.get("data", {}).get("result", [])
            else:
                print(f"❌ Query failed: {data.get('error', 'Unknown error')}")
                return []
    except Exception as e:
        print(f"❌ Query error: {e}")
        return []


def prom_query_range(
    base_url: str, promql: str, start: int, end: int, step: str
) -> List[Dict[str, Any]]:
    """查询 Prometheus range query API"""
    url = base_url.rstrip("/") + "/api/v1/query_range"
    params = urllib.parse.urlencode({"query": promql, "start": start, "end": end, "step": step})
    full_url = url + "?" + params

    try:
        with urllib.request.urlopen(full_url, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") == "success":
                return data.get("data", {}).get("result", [])
            else:
                print(f"❌ Range query failed: {data.get('error', 'Unknown error')}")
                return []
    except Exception as e:
        print(f"❌ Range query error: {e}")
        return []


def discover_instances(base_url: str) -> List[str]:
    """自动发现 node_exporter 实例"""
    print("🔍 Discovering node_exporter instances...")

    # 尝试查询 node job
    results = prom_query(base_url, 'up{job=~".*node.*"}')

    # 如果没有结果，回退到所有 up 指标
    if not results:
        print("   No node jobs found, trying all 'up' metrics...")
        results = prom_query(base_url, "up")

    instances = []
    for result in results:
        metric = result.get("metric", {})
        instance = metric.get("instance", "")
        if instance and instance not in instances:
            instances.append(instance)

    print(f"✅ Found {len(instances)} instance(s): {', '.join(instances)}")
    return instances


def collect_metrics(base_url: str, instance: str) -> Dict[str, Any]:
    """收集指定实例的所有指标"""
    print(f"📊 Collecting metrics for {instance}...")

    metrics = {}

    # CPU 指标
    cpu_queries = {
        "cpu_user": 'avg by(instance)(irate(node_cpu_seconds_total{{instance="{inst}",mode="user"}}[5m])) * 100'.format(
            inst=instance
        ),
        "cpu_system": 'avg by(instance)(irate(node_cpu_seconds_total{{instance="{inst}",mode="system"}}[5m])) * 100'.format(
            inst=instance
        ),
        "cpu_idle": 'avg by(instance)(irate(node_cpu_seconds_total{{instance="{inst}",mode="idle"}}[5m])) * 100'.format(
            inst=instance
        ),
        "cpu_iowait": 'avg by(instance)(irate(node_cpu_seconds_total{{instance="{inst}",mode="iowait"}}[5m])) * 100'.format(
            inst=instance
        ),
    }

    for key, query in cpu_queries.items():
        results = prom_query(base_url, query)
        if results and len(results) > 0:
            value = results[0].get("value", [None, None])[1]
            metrics[key] = float(value) if value else 0.0
        else:
            metrics[key] = 0.0

    # 内存指标
    mem_used_query = '(1 - node_memory_MemAvailable_bytes{{instance="{inst}"}} / node_memory_MemTotal_bytes{{instance="{inst}"}}) * 100'.format(
        inst=instance
    )
    results = prom_query(base_url, mem_used_query)
    if results and len(results) > 0:
        value = results[0].get("value", [None, None])[1]
        metrics["memory_used_percent"] = float(value) if value else 0.0
    else:
        metrics["memory_used_percent"] = 0.0

    mem_total_query = 'node_memory_MemTotal_bytes{{instance="{inst}"}} / 1024 / 1024 / 1024'.format(
        inst=instance
    )
    results = prom_query(base_url, mem_total_query)
    if results and len(results) > 0:
        value = results[0].get("value", [None, None])[1]
        metrics["memory_total_gb"] = float(value) if value else 0.0
    else:
        metrics["memory_total_gb"] = 0.0

    mem_avail_query = (
        'node_memory_MemAvailable_bytes{{instance="{inst}"}} / 1024 / 1024 / 1024'.format(
            inst=instance
        )
    )
    results = prom_query(base_url, mem_avail_query)
    if results and len(results) > 0:
        value = results[0].get("value", [None, None])[1]
        metrics["memory_available_gb"] = float(value) if value else 0.0
    else:
        metrics["memory_available_gb"] = 0.0

    # 磁盘指标
    disk_used_query = '(1 - node_filesystem_avail_bytes{{instance="{inst}",mountpoint="/",fstype!="tmpfs"}} / node_filesystem_size_bytes{{instance="{inst}",mountpoint="/",fstype!="tmpfs"}}) * 100'.format(
        inst=instance
    )
    results = prom_query(base_url, disk_used_query)
    if results and len(results) > 0:
        value = results[0].get("value", [None, None])[1]
        metrics["disk_used_percent"] = float(value) if value else 0.0
    else:
        metrics["disk_used_percent"] = 0.0

    disk_read_query = 'sum(irate(node_disk_read_bytes_total{{instance="{inst}"}}[5m]))'.format(
        inst=instance
    )
    results = prom_query(base_url, disk_read_query)
    if results and len(results) > 0:
        value = results[0].get("value", [None, None])[1]
        metrics["disk_read_bytes_per_sec"] = float(value) if value else 0.0
    else:
        metrics["disk_read_bytes_per_sec"] = 0.0

    disk_write_query = 'sum(irate(node_disk_written_bytes_total{{instance="{inst}"}}[5m]))'.format(
        inst=instance
    )
    results = prom_query(base_url, disk_write_query)
    if results and len(results) > 0:
        value = results[0].get("value", [None, None])[1]
        metrics["disk_write_bytes_per_sec"] = float(value) if value else 0.0
    else:
        metrics["disk_write_bytes_per_sec"] = 0.0

    # 网络指标
    net_rx_query = (
        'sum(irate(node_network_receive_bytes_total{{instance="{inst}",device!="lo"}}[5m]))'.format(
            inst=instance
        )
    )
    results = prom_query(base_url, net_rx_query)
    if results and len(results) > 0:
        value = results[0].get("value", [None, None])[1]
        metrics["network_receive_bytes_per_sec"] = float(value) if value else 0.0
    else:
        metrics["network_receive_bytes_per_sec"] = 0.0

    net_tx_query = 'sum(irate(node_network_transmit_bytes_total{{instance="{inst}",device!="lo"}}[5m]))'.format(
        inst=instance
    )
    results = prom_query(base_url, net_tx_query)
    if results and len(results) > 0:
        value = results[0].get("value", [None, None])[1]
        metrics["network_transmit_bytes_per_sec"] = float(value) if value else 0.0
    else:
        metrics["network_transmit_bytes_per_sec"] = 0.0

    # 负载指标
    for load_metric in ["node_load1", "node_load5", "node_load15"]:
        query = '{metric}{{instance="{inst}"}}'.format(metric=load_metric, inst=instance)
        results = prom_query(base_url, query)
        if results and len(results) > 0:
            value = results[0].get("value", [None, None])[1]
            metrics[load_metric] = float(value) if value else 0.0
        else:
            metrics[load_metric] = 0.0

    return metrics


def collect_baselines(base_urlance: str) -> Dict[str, float]:
    """收集7天基线数据"""
    print(f"📈 Collecting 7-day baselines for {instance}...")

    now = int(datetime.now().timestamp())
    start = now - 7 * 24 * 3600  # 7天前

    baselines = {}

    # 基线查询
    baseline_queries = {
        "cpu_user_baseline": 'avg by(instance)(irate(node_cpu_seconds_total{{instance="{inst}",mode="user"}}[5m])) * 100'.format(
            inst=instance
        ),
        "cpu_system_baseline": 'avg by(instance)(irate(node_cpu_seconds_total{{instance="{inst}",mode="system"}}[5m])) * 100'.format(
            inst=instance
        ),
        "cpu_idle_baseline": 'avg by(instance)(irate(node_cpu_seconds_total{{instance="{inst}",mode="idle"}}[5m])) * 100'.format(
            inst=instance
        ),
        "memory_used_percent_baseline": '(1 - node_memory_MemAvailable_bytes{{instance="{inst}"}} / node_memory_MemTotal_bytes{{instance="{inst}"}}) * 100'.format(
            inst=instance
        ),
        "disk_used_percent_baseline": '(1 - node_filesystem_avail_bytes{{instance="{inst}",mountpoint="/",fstype!="tmpfs"}} / node_filesystem_size_bytes{{instance="{inst}",mountpoint="/",fstype!="tmpfs"}}) * 100'.format(
            inst=instance
        ),
        "load1_baseline": 'node_load1{{instance="{inst}"}}'.format(inst=instance),
    }

    for key, query in baseline_queries.items():
        results = prom_query_range(base_url, query, start, now, "1h")
        if results and len(results) > 0:
            values = results[0].get("values", [])
            if values:
                # 计算平均值
                sum_val = sum(float(v[1]) for v in values if v[1] != "NaN")
                count = sum(1 for v in values if v[1] != "NaN")
                baselines[key] = sum_val / count if count > 0 else 0.0
            else:
                baselines[key] = 0.0
        else:
            baselines[key] = 0.0

    return baselines


def format_model_input(instance: str, metrics: Dict[str, Any], baselines: Dict[str, float]) -> str:
    """格式化为模型输入格式"""
    now = datetime.now()
    time_start(now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
    time_end = now.strftime("%Y-%m-%d %H:%M")

    lines = [
        f"时间范围: {time_start} - {time_end}",
        f"实例: {instance}",
        "",
        f'node_cpu_seconds_total{{mode="user"}} {metrics.get("cpu_user", 0):.1f}%',
        f'node_cpu_seconds_total{{mode="system"}} {metrics.get("cpu_system", 0):.1f}%',
        f'node_cpu_seconds_total{{mode="idle"}} {metrics.get("cpu_idle", 0):.1f}%',
        f'node_cpu_seconds_total{{mode="iowait"}} {metrics.get("cpu_iowait", 0):.1f}%',
        f"node_memory_used_percent {metrics.get('memory_used_percent', 0):.1f}%",
        f"node_memory_MemTotal_bytes (GB) {metrics.get('memory_total_gb', 0):.2f}",
        f"node_memory_MemAvailable_bytes (GB) {metrics.get('memory_available_gb', 0):.2f}",
        f"node_filesystem_used_percent (/) {metrics.get('disk_used_percent', 0):.1f}%",
        f"node_disk_read_bytes_total (bytes/s) {metrics.get('disk_read_bytes_per_sec', 0):.0f}",
        f"node_disk_written_bytes_total (bytes/s) {metrics.get('disk_write_bytes_per_sec', 0):.0f}",
        f"node_network_receive_bytes_total (bytes/s) {metrics.get('network_receive_bytes_per_sec', 0):.0f}",
        f"node_network_transmit_bytes_total (bytes/s) {metrics.get('network_transmit_bytes_per_sec', 0):.0f}",
        f"node_load1 {metrics.get('node_load1', 0):.2f}",
        f"node_load5 {metrics.get('node_load5', 0):.2f}",
        f"node_load15 {metrics.get('node_load15', 0):.2f}",
        "",
        "基线数据 (过去7天平均):",
        f'node_cpu_seconds_total{{mode="user"}}: {baselines.get("cpu_user_baseline", 0):.1f}%',
        f'node_cpu_seconds_total{{mode="system"}}: {baselines.get("cpu_system_baseline", 0):.1f}%',
        f'node_cpu_seconds_total{{mode="idle"}}: {baselines.get("cpu_idle_baseline", 0):.1f}%',
        f"node_memory_used_percent: {baselines.get('memory_used_percent_baseline', 0):.1f}%",
        f"node_filesystem_used_percent (/): {baselines.get('disk_used_percent_baseline', 0):.1f}%",
        f"node_load1: {baselines.get('load1_baseline', 0):.2f}",
    ]

    return "\n".join(lines)


def call_llm(llm_url: str, model: str, prompt: str) -> Optional[str]:
    """调用本地 LLM API"""
    url = llm_url.rstrip("/") + "/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是一个专业的基础设施监控助手,负责分析 Prometheus 指标数据并提供巡检报告。请根据提供的指标数据进行分析,识别异常,给出判断和建议。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1024,
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", "Authorization": "Bearer none"}
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
            choices = result.get("choices", [])
            if choices and len(choices) > 0:
                message = choices[0].get("message", {})
                return message.get("content", "")
            else:
                print("❌ No response from LLM")
                return None
    except Exception as e:
        print(f"❌ LLM API error: {e}")
        return None


def inspect_instance(
    base_url: str, llm_url: str, model: str, instance: str
) -> Optional[Dict[str, Any]]:
    """巡检单个实例"""
    print(f"\n{'=' * 60}")
    print(f"🔍 Inspecting instance: {instance}")
    print(f"{'=' * 60}")

    try:
        # 收集指标
        metrics = collect_metrics(base_url, instance)

        # 收集基线
        baselines = collect_baselines(base_url, instance)

        # 格式化输入
        model_input = format_model_input(instance, metrics, baselines)

        print("\n📝 Model input:")
        print("-" * 60)
        print(model_input)
        print("-" * 60)

        # 调用 LLM
        print("\n🤖 Calling LLM for analysis...")
        report = call_llm(llm_url, model, model_input)

        if report:
            print("\n📋 Inspection Report:")
            print("-" * 60)
            print(report)
            print("-" * 60)

            return {
                "instance": instance,
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics,
                "baselines": baselines,
                "model_input": model_input,
                "report": report,
                "status": "success",
            }
        else:
            return {
                "instance": instance,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": "LLM returned no response",
            }

    except Exception as e:
        print(f"❌ Error inspecting {instance}: {e}")
        return {
            "instance": instance,
            "timestamp": datetime.now().isoformat(),
            "status": "failed",
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Prometheus 巡检脚本 - 直接查询 Prometheus API 并调用本地 LLM 分析"
    )
    parser.add_argument(
        "--prometheus-url",
        default="http://172.16.12.114:31909",
        help="Prometheus 服务器 URL (默认: http://172.16.12.114:31909)",
    )
    parser.add_argument(
        "--llm-url",
        default="http://localhost:8080/v1",
        help="LLM API URL (默认: http://localhost:8080/v1)",
    )
    parser.add_argument("--model", default="default", help="LLM 模型名称 (默认: default)")
    parser.add_argument("--instance", default=None, help="指定实例 (默认: 自动发现所有实例)")
    parser.add_argument(
        "--output",
        default="outputs/inspection_report.json",
        help="输出 JSON 文件路径 (默认: outputs/inspection_report.json)",
    )

    args = parser.parse_args()

    # 打印横幅
    print("\n" + "=" * 60)
    print("🚀 Prometheus 巡检脚本")
    print("=" * 60)
    print(f"📍 Prometheus URL: {args.prometheus_url}")
    print(f"🤖 LLM URL: {args.llm_url}")
    print(f"📦 Model: {args.model}")
    print("=" * 60 + "\n")

    # 发现或使用指定实例
    if args.instance:
        instances = [args.instance]
        print(f"✅ Using specified instance: {args.instance}")
    else:
        instances = discover_instances(args.prometheus_url)

    if not instances:
        print("❌ No instances found!")
        sys.exit(1)

    # 巡检所有实例
    results = []
    success_count = 0

    for instance in instances:
        result = inspect_instance(args.prometheus_url, args.llm_url, args.model, instance)
        if result:
            results.append(result)
            if result.get("status") == "success":
                success_count += 1

    # 保存结果
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "timestamp": datetime.now().isoformat(),
        "prometheus_url": args.prometheus_url,
        "llm_url": args.llm_url,
        "model": args.model,
        "total_instances": len(instances),
        "success_count": success_count,
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print("\n" + "=" * 60)
    print("📊 Inspection Summary")
    print("=" * 60)
    print(f"✅ Successfully inspected: {success_count}/{len(instances)} instances")
    print(f"💾 Report saved to: {output_path}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
