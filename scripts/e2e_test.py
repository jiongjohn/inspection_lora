#!/usr/bin/env python3
"""
端到端测试脚本 - 基于真实 Prometheus 指标场景测试微调模型输出质量

包含 10 个硬编码的真实监控场景，测试模型在不同严重程度和指标组合下的表现。
评分标准：严重程度判断、结构化输出、关键词覆盖、建议质量、文本连贯性。
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler


# 系统提示词
SYSTEM_PROMPT = "你是一个专业的基础设施监控助手,负责分析 Prometheus 指标数据并提供巡检报告。请根据提供的指标数据进行分析,识别异常,给出判断和建议。"


# 10 个测试场景
TEST_SCENARIOS = [
    {
        "name": "CPU 突增",
        "input": """时间范围: 2026-02-25 14:00 - 2026-02-25 15:00
实例: node-web-01:9100

node_cpu_seconds_total{cpu="0",mode="user"} 92.5
node_cpu_seconds_total{cpu="0",mode="system"} 5.3
node_cpu_seconds_total{cpu="0",mode="idle"} 2.2
node_load1 8.5
node_load5 7.2
node_load15 6.8

基线数据 (过去7天平均):
node_cpu_seconds_total{mode="user"}: 35.0
node_cpu_seconds_total{mode="system"}: 3.5
node_cpu_seconds_total{mode="idle"}: 61.5
node_load1: 2.1""",
        "expected_severity": "critical",
        "expected_keywords": ["CPU", "突增", "异常", "负载", "建议"]
    },
    {
        "name": "内存正常",
        "input": """时间范围: 2026-02-25 14:00 - 2026-02-25 15:00
实例: node-db-02:9100

node_memory_MemTotal_bytes 16777216000
node_memory_MemAvailable_bytes 8388608000
node_memory_MemFree_bytes 4194304000
node_memory_Buffers_bytes 2097152000
node_memory_Cached_bytes 2097152000

基线数据 (过去7天平均):
node_memory_MemAvailable_bytes: 8500000000
node_memory_MemFree_bytes: 4300000000""",
        "expected_severity": "normal",
        "expected_keywords": ["内存", "正常", "健康", "稳定"]
    },
    {
        "name": "磁盘空间不足",
        "input": """时间范围: 2026-02-25 14:00 - 2026-02-25 15:00
实例: node-storage-03:9100

node_filesystem_size_bytes{mountpoint="/"} 107374182400
node_filesystem_avail_bytes{mountpoint="/"} 5368709120
node_filesystem_files{mountpoint="/"} 6553600
node_filesystem_files_free{mountpoint="/"} 327680

基线数据 (过去7天平均):
node_filesystem_avail_bytes{mountpoint="/"}: 21474836480""",
        "expected_severity": "warning",
        "expected_keywords": ["磁盘", "空间", "不足", "清理", "扩容"]
    },
    {
        "name": "网络流量突增",
        "input": """时间范围: 2026-02-25 14:00 - 2026-02-25
实例: node-gateway-04:9100

node_network_receive_bytes_total{device="eth0"} 524288000000
node_network_transmit_bytes_total{device="eth0"} 419430400000
node_network_receive_packets_total{device="eth0"} 350000000
node_network_transmit_packets_total{device="eth0"} 280000000

基线数据 (过去7天平均):
node_network_receive_bytes_total{device="eth0"}: 104857600000
node_network_transmit_bytes_total{device="eth0"}: 83886080000""",
        "expected_severity": "critical",
        "expected_keywords": ["网络", "流量", "突增", "带宽", "异常"]
    },
    {
        "name": "CPU + 内存双重异常",
        "input": """时间范围: 2026-02-25 14:00 - 2026-02-25 15:00
实例: node-app-05:9100

node_cpu_seconds_total{cpu="0",mode="user"} 88.3
node_cpu_seconds_total{cpu="0",mode="system"} 9.2
node_cpu_seconds_total{cpu="0",mode="idle"} 2.5
node_memory_MemTotal_bytes 8589934592
node_memory_MemAvailable_bytes 429496729
node_memory_MemFree_bytes 104857600
node_load1 12.5

基线数据 (过去7天平均):
node_cpu_seconds_total{mode="user"}: 40.0
node_memory_MemAvailable_bytes: 4294967296
node_load1: 3.2""",
        "expected_severity": "critical",
        "expected_keywords": ["CPU", "内存", "双重", "异常", "紧急", "资源"]
    },
    {
        "name": "系统全面健康",
        "input": """时间范围: 2026-02-25 14:00 - 2026-02-25 15:00
实例: node-prod-06:9100

node_cpu_seconds_total{cpu="0",mode="user"} 42.0
node_cpu_seconds_total{cpu="0",mode="system"} 3.8
node_cpu_seconds_total{cpu="0",mode="idle"} 54.2
node_memory_MemTotal_bytes 16777216000
node_memory_MemAvailable_bytes 10737418240
node_filesystem_avail_bytes{mountpoint="/"} 53687091200
node_load1 2.3
node_load5 2.1

基线数据 (过去7天平均):
node_cpu_seconds_total{mode="user"}: 40.5
node_memory_vailable_bytes: 10500000000
node_load1: 2.2""",
        "expected_severity": "normal",
        "expected_keywords": ["正常", "健康", "稳定", "良好"]
    },
    {
        "name": "磁盘 IO 饱和",
        "input": """时间范围: 2026-02-25 14:00 - 2026-02-25 15:00
实例: node-db-07:9100

node_disk_io_time_seconds_total{device="sda"} 3420.5
node_disk_read_bytes_total{device="sda"} 524288000000
node_disk_write_bytes_total{device="sda"} 419430400000
node_disk_io_time_weighted_seconds_total{device="sda"} 5832.8
node_load1 15.2

基线数据 (过去7天平均):
node_disk_io_time_seconds_total{device="sda"}: 850.0
node_disk_read_bytes_total{device="sda"}: 104857600000
node_load1: 3.5""",
        "expected_severity": "critical",
        "expected_keywords": ["磁盘", "IO", "饱和", "性能", "瓶颈"]
    },
    {
        "name": "内存泄漏趋势",
        "input": """时间范围: 2026-02-25 14:00 - 2026-02-25 15:00
实例: node-service-08:9100

node_memory_MemTotal_bytes 8589934592
node_memory_MemAvailable_bytes 1717986918
node_memory_MemFree_bytes 429496729
node_memory_Cached_bytes 858993459
node_memory_Buffers_bytes
基线数据 (过去7天平均):
node_memory_MemAvailable_bytes: 4294967296
node_memory_MemFree_bytes: 2147483648""",
        "expected_severity": "warning",
        "expected_keywords": ["内存", "泄漏", "趋势", "持续", "监控"]
    },
    {
        "name": "负载与 CPU 背离",
        "input": """时间范围: 2026-02-25 14:00 - 2026-02-25 15:00
实例: node-worker-09:9100

node_cpu_seconds_total{cpu="0",mode="user"} 38.5
node_cpu_seconds_total{cpu="0",mode="system"} 4.2
node_cpu_seconds_total{cpu="0",mode="idle"} 52.3
node_cpu_seconds_total{cpu="0",mode="iowait"} 5.0
node_load1 9.8
node_load5 8.5
node_load15 7.2

基线数据 (过去7天平均):
node_cpu_seconds_total{mode="user"}: 40.0
node_load1: 2.5""",
        "expected_severity": "warning",
        "expected_keywords": ["负载", "CPU", "背离", "IO", "等待"]
    },
    {
        "name": "全栈退化",
        "input": """时间范围: 2026-02-25 14:00 - 2026-02-25 15:00
实例: node-critical-10:9100

node_cpu_seconds_total{cpu="0",mode="user"} 85.2
node_cpu_seconds_total{cpu="0",mode="system"} 12.3
node_cpu_seconds_total{cpu="0",mode="idle"} 2.5
node_memory_MemTotal_bytes 16777216000
node_memory_MemAvailable_bytes 838860800
node_filesystem_avail_bytes{mountpoint="/"} 2147483648
node_disk_io_time_seconds_total{device="sda"} 3250.0
node_network_receive_bytes_total{device="eth0"} 524288000000
node_load1 18.5

基线数据 (过去7天平均):
node_cpu_seconds_total{mode="user"}: 42.0
node_memory_MemAvailable_bytes: 8388608000
node_filesystem_avail_bytes{mountpoint="/"}: 32212254720
node_load1: 3.0""",
        "expected_severity": "critical",
        "expected_keywords": ["全面", "退化", "严重", "紧急", "多项", "异常"]
    }
]


def score_output(output: str, expected_severity: str, expected_keywords: List[str]) -> Tuple[float, Dict]:
    """
    评分函数 (0-5 分制)

    评分维度:
    1. 严重程度正确 (+1.0)
    2. 结构化输出 (+1.0)
    3. 关键词覆盖 (+1.0)
    4. 编号建议 (+1.0)
    5. 文本连贯性 (+1.0)
    """
    score = 0.0
    details = {}

    # 1. 严重程度判断
    severity_map = {
        "critical": ["🔴", "严重", "紧急", "critical"],
        "warning": ["🟡", "警告", "注意", "warning", "偏高", "偏低", "预警"],
        "normal": ["🟢", "正常", "健康", "良好", "normal"]
    }

    severity_correct = any(marker in output for marker in severity_map[expected_severity])
    if severity_correct:
        score += 1.0
    details["severity_correct"] = severity_correct

    # 2. 结构化输出 (包含关键章节)
    structure_keywords = ["巡检结果", "异常发现", "判断", "建议", "指标概览", "指标详情"]
    structure_count = sum(1 for kw in structure_keywords if kw in output)
    if structure_count >= 2:
        score += 1.0
    details["structure_sections"] = structure_count

    # 3. 关键词覆盖
    keyword_matches = sum(1 for kw in expected_keywords if kw in output)
    keyword_ratio = keyword_matches / len(expected_keywords) if expected_keywords else 0
    score += keyword_ratio
    details["keyword_coverage"] = f"{keyword_matches}/{len(expected_keywords)}"

    # 4. 编号建议
    has_numbered_recommendations = bool(re.search(r'[1-4]\.\s*[\u4e00-\u9fff]', output))
    if has_numbered_recommendations:
        score += 1.0
    details["has_numbered_recommendations"] = has_numbered_recommendations

    # 5. 文本连贯性 (长度 > 50 字符，包含中文)
    is_coherent = len(output) > 50 and bool(re.search(r'[\u4e00-\u9fff]', output))
    if is_coherent:
        score += 1.0
    details["is_coherent"] = is_coherent
    details["output_length"] = len(output)

    return score, details


def run_scenario_inference(model, tokenizer, scenario: Dict, max_tokens: int) -> str:
    """运行单个场景的推理"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": scenario["input"]}
    ]

    prompt = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=False
    )

    sampler = make_sampler(temp=0.1)
    response = generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        sampler=sampler,
        verbose=False
    )

    return response


def main():
    parser = argparse.ArgumentParser(description="端到端测试脚本 - 测试微调模型输出质量")
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct", help="基础模型路径")
    parser.add_argument("--adapter-path", default="outputs/adapters", help="适配器路径")
    parser.add_argument("--max-tokens", type=int, default=512, help="最大生成 token 数")
    parser.add_argument("--output", default="outputs/e2e_results.json", help="结果输出路径")
    args = parser.parse_args()

    print(f"加载模型: {args.model}")
    print(f"适配器路径: {args.adapter_path}")

    model, tokenizer = load(args.model, adapter_path=args.adapter_path)

    print("\n" + "=" * 60)
    print("开始端到端测试 (10 个场景)")
    print("=" * 60 + "\n")

    results = []
    total_score = 0.0

    for idx, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"[{idx}/10] 测试场景: {scenario['name']}")

        # 运行推理
        output = run_scenario_inference(model, tokenizer, scenario, args.max_tokens)

        # 评分
        score, details = score_output(
            output,
            scenario["expected_severity"],
            scenario["expected_keywords"]
        )

        total_score += score

        # 记录结果
        result = {
            "scenario_id": idx,
            "name": scenario["name"],
            "expected_severity": scenario["expected_severity"],
            "score": round(score, 2),
            "max_score": 5.0,
            "details": details,
            "output": output
        }
        results.append(result)

        # 打印单个场景结果
        status = "✅" if score >= 3.0 else "❌"
        print(f"   评分: {score:.1f}/5.0 {status}\n")

    # 计算平均分
    avg_score = total_score / len(TEST_SCENARIOS)
    passed = avg_score > 3.0

    # 打印汇总结果
    print("=" * 60)
    print("端到端测试结果")
    print("=" * 60)
    for idx, result in enumerate(results, 1):
        status = "✅" if result["score"] >= 3.0 else "❌"
        print(f"{idx}. {result['name']}: {result['score']:.1f}/5.0 {status}")

    print(f"\n平均评分: {avg_score:.1f}/5.0")
    print(f"通过标准: > 3.0/5.0 → {'✅ 通过' if passed else '❌ 未通过'}")
    print("=" * 60)

    # 写入 JSON 结果
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary = {
        "total_scenarios": len(TEST_SCENARIOS),
        "average_score": round(avg_score, 2),
        "passed": passed,
        "pass_threshold": 3.0,   "results": results
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n详细结果已写入: {output_path}")


if __name__ == "__main__":
    main()
