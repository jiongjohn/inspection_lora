#!/usr/bin/env python3
"""数据质量过滤脚本。

对生成的原始训练数据进行多阶段过滤:
1. JSON 格式校验
2. Schema 完整性检查 (messages 结构)
3. 内容合理性检查
4. 长度过滤
5. 去重
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

# 允许导入 src 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from inspection_lora.data_utils import SYSTEM_PROMPT


def parse_args():
    parser = argparse.ArgumentParser(description="过滤训练数据")
    parser.add_argument(
        "--input",
        type=str,
        default="data/generated/raw_data.jsonl",
        help="输入 JSONL 文件路径",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/generated/filtered_data.jsonl",
        help="输出 JSONL 文件路径",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=100,
        help="最小字符数 (user + assistant content)",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=6000,
        help="最大字符数 (user + assistant content)",
    )
    return parser.parse_args()


def check_json(line: str, line_num: int) -> dict | None:
    """阶段1: JSON 格式校验。"""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def check_schema(record: dict) -> bool:
    """阶段2: Schema 完整性检查。"""
    messages = record.get("messages")
    if not isinstance(messages, list) or len(messages) != 3:
        return False
    expected_roles = ["system", "user", "assistant"]
    for msg, expected_role in zip(messages, expected_roles):
        if not isinstance(msg, dict):
            return False
        if msg.get("role") != expected_role:
            return False
        if not isinstance(msg.get("content"), str):
            return False
    return True


def check_content(record: dict) -> bool:
    """阶段3: 内容合理性检查。"""
    messages = record["messages"]
    system_content = messages[0]["content"]
    user_content = messages[1]["content"]
    assistant_content = messages[2]["content"]

    # system prompt 应匹配
    if system_content != SYSTEM_PROMPT:
        return False

    # user 和 assistant 内容不能为空
    if len(user_content.strip()) < 10:
        return False
    if len(assistant_content.strip()) < 20:
        return False

    # assistant 回复应包含巡检相关关键词
    keywords = ["巡检", "异常", "正常", "建议", "判断", "指标", "评分", "报告", "分析"]
    if not any(kw in assistant_content for kw in keywords):
        return False

    return True


def check_length(record: dict, min_len: int, max_len: int) -> bool:
    """阶段4: 长度过滤。"""
    messages = record["messages"]
    total_len = len(messages[1]["content"]) + len(messages[2]["content"])
    return min_len <= total_len <= max_len


def content_hash(record: dict) -> str:
    """计算内容哈希用于去重。"""
    messages = record["messages"]
    key = messages[1]["content"] + "|||" + messages[2]["content"]
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"❌ 输入文件不存在: {input_path}")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 统计
    stats = {
        "total": 0,
        "json_fail": 0,
        "schema_fail": 0,
        "content_fail": 0,
        "length_fail": 0,
        "duplicate": 0,
        "passed": 0,
    }

    seen_hashes: set[str] = set()
    passed_records: list[dict] = []

    with open(input_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            stats["total"] += 1

            # 阶段1: JSON
            record = check_json(line, line_num)
            if record is None:
                stats["json_fail"] += 1
                continue

            # 阶段2: Schema
            if not check_schema(record):
                stats["schema_fail"] += 1
                continue

            # 阶段3: 内容
            if not check_content(record):
                stats["content_fail"] += 1
                continue

            # 阶段4: 长度
            if not check_length(record, args.min_length, args.max_length):
                stats["length_fail"] += 1
                continue

            # 阶段5: 去重
            h = content_hash(record)
            if h in seen_hashes:
                stats["duplicate"] += 1
                continue
            seen_hashes.add(h)

            passed_records.append(record)
            stats["passed"] += 1

    # 写入
    with open(output_path, "w", encoding="utf-8") as f:
        for record in passed_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 报告
    print(f"📊 数据过滤报告:")
    print(f"  总计: {stats['total']} 条")
    print(f"  JSON 格式错误: {stats['json_fail']} 条")
    print(f"  Schema 不合格: {stats['schema_fail']} 条")
    print(f"  内容不合格: {stats['content_fail']} 条")
    print(f"  长度不合格: {stats['length_fail']} 条")
    print(f"  重复: {stats['duplicate']} 条")
    print(f"  ✅ 通过: {stats['passed']} 条")
    print(f"  输出: {output_path}")


if __name__ == "__main__":
    main()
