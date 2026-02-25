#!/usr/bin/env python3
"""数据合成编排脚本。

使用模板引擎生成 ScenarioConfig，通过 prompt_builder 转换为 mlx-lm chat messages 格式。
"""

import argparse
import json
import random
import sys
from pathlib import Path

# 允许导入 src 包和 data 包
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from data.templates import generate_scenarios
from inspection_lora.prompt_builder import build_chat_messages


# 场景类型分布 (目标 2000 条 MVP)
SCENARIO_DISTRIBUTION = {
    "single_anomaly": 0.25,  # 500
    "multi_metric": 0.20,  # 400
    "normal": 0.20,  # 400
    "capacity": 0.15,  # 300
    "health": 0.10,  # 200
    "report": 0.10,  # 200
}


def parse_args():
    parser = argparse.ArgumentParser(description="生成训练数据")
    parser.add_argument(
        "--count",
        type=int,
        default=2000,
        help="生成样本总数",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/generated/raw_data.jsonl",
        help="输出 JSONL 文件路径",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    rng = random.Random(args.seed)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_records = []
    total = args.count

    print(f"🚀 开始生成 {total} 条训练数据 (seed={args.seed})")
    print(f"   场景分布:")

    for scenario_type, ratio in SCENARIO_DISTRIBUTION.items():
        count = int(total * ratio)
        # 确保最后一个类型补齐总数
        if scenario_type == list(SCENARIO_DISTRIBUTION.keys())[-1]:
            count = total - len(all_records)

        print(f"   - {scenario_type}: {count} 条 ({ratio * 100:.0f}%)")

        configs = generate_scenarios(scenario_type, count, rng)

        for config in configs:
            record = build_chat_messages(config)
            all_records.append(record)

    # 打乱顺序
    rng.shuffle(all_records)

    # 写入
    with open(output_path, "w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n✅ 数据生成完成:")
    print(f"   总计: {len(all_records)} 条")
    print(f"   输出: {output_path}")

    # 抽样展示
    print(f"\n📋 随机抽样 3 条:")
    samples = rng.sample(all_records, k=min(3, len(all_records)))
    for i, sample in enumerate(samples, 1):
        msgs = sample["messages"]
        user_preview = msgs[1]["content"][:80].replace("\n", " ")
        assistant_preview = msgs[2]["content"][:80].replace("\n", " ")
        print(f"   [{i}] user: {user_preview}...")
        print(f"       assistant: {assistant_preview}...")


if __name__ == "__main__":
    main()
