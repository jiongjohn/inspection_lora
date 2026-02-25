#!/usr/bin/env python3
"""数据集切分脚本。

将过滤后的数据按 80/10/10 切分为 train/valid/test。
"""

import argparse
import json
import random
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="切分训练数据集")
    parser.add_argument(
        "--input",
        type=str,
        default="data/generated/filtered_data.jsonl",
        help="输入 JSONL 文件路径",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed",
        help="输出目录",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.8,
        help="训练集比例",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.1,
        help="验证集比例",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f"❌ 输入文件不存在: {input_path}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 读取所有记录
    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    total = len(records)
    if total == 0:
        print("❌ 输入文件为空")
        sys.exit(1)

    # 打乱
    rng = random.Random(args.seed)
    rng.shuffle(records)

    # 切分
    train_end = int(total * args.train_ratio)
    val_end = train_end + int(total * args.val_ratio)

    splits = {
        "train.jsonl": records[:train_end],
        "valid.jsonl": records[train_end:val_end],
        "test.jsonl": records[val_end:],
    }

    # 写入
    for filename, data in splits.items():
        filepath = output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            for record in data:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"✅ 数据集切分完成 (seed={args.seed}):")
    for filename, data in splits.items():
        print(f"  {filename}: {len(data)} 条")
    print(f"  总计: {total} 条")
    print(f"  输出目录: {output_dir}")


if __name__ == "__main__":
    main()
