#!/usr/bin/env python3
"""
Prometheus 指标 AI 巡检推理脚本

使用微调后的 MLX LoRA 模型对 Prometheus 指标数据进行智能分析和巡检。
支持单条推理和批量推理两种模式。
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler


DEFAULT_SYSTEM_PROMPT = (
    "你是一个专业的基础设施监控助手,负责分析 Prometheus 指标数据并提供巡检报告。"
    "请根据提供的指标数据进行分析,识别异常,给出判断和建议。"
)


def load_model(model_path: str, adapter_path: Optional[str] = None):
    """加载模型和分词器"""
    print(f"Loading model: {model_path}")
    if adapter_path:
        print(f"Loading adapter: {adapter_path}")
        model, tokenizer = load(model_path, adapter_path=adapter_path)
    else:
        print("Loading base model without adapter")
        model, tokenizer = load(model_path)
    print("Model loaded successfully")
    return model, tokenizer


def run_inference(
    model,
    tokenizer,
    prompt: str,
    max_tokens: int = 512,
    temp: float = 0.1,
) -> str:
    """运行单次推理"""
    sampler = make_sampler(temp=temp)
    response = generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        sampler=sampler,
        verbose=False,
    )
    return response


def build_chat_prompt(
    tokenizer,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """构建聊天格式的提示词"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    prompt = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=False,
    )
    return prompt


def single_inference(
    model,
    tokenizer,
    user_prompt: str,
    max_tokens: int,
    temp: float,
):
    """单条推理模式"""
    prompt = build_chat_prompt(tokenizer, DEFAULT_SYSTEM_PROMPT, user_prompt)
    print("Running inference...")
    response = run_inference(model, tokenizer, prompt, max_tokens, temp)
    print("\n" + "=" * 80)
    print("Generated Response:")
    print("=" * 80)
    print(response)
    print("=" * 80)


def batch_inference(
    model,
    tokenizer,
    input_path: str,
    output_path: str,
    max_tokens: int,
    temp: float,
):
    """批量推理模式"""
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading test data from: {input_path}")
    print(f"Output will be written to: {output_path}")

    results = []
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total = len(lines)
    print(f"Processing {total} samples...")

    for idx, line in enumerate(lines, 1):
        data = json.loads(line.strip())
        messages = data["messages"]

        # 提取系统提示、用户输入和期望输出
        system_content = (
            messages[0]["content"] if messages[0]["role"] == "system" else DEFAULT_SYSTEM_PROMPT
        )
        user_content = (
            messages[1]["content"] if len(messages) > 1 and messages[1]["role"] == "user" else ""
        )
        expected_content = (
            messages[2]["content"]
            if len(messages) > 2 and messages[2]["role"] == "assistant"
            else ""
        )

        # 构建提示词
        prompt = build_chat_prompt(tokenizer, system_content, user_content)

        # 运行推理
        generated = run_inference(model, tokenizer, prompt, max_tokens, temp)

        # 保存结果
        result = {
            "input": user_content,
            "expected": expected_content,
            "generated": generated,
        }

        # 如果有 scenario_type 字段，也保存
        if "scenario_type" in data:
            result["scenario_type"] = data["scenario_type"]

        results.append(result)

        # 显示进度
        if idx % 10 == 0 or idx == total:
            print(f"Progress: {idx}/{total} samples processed")

    # 写入输出文件
    print(f"\nWriting results to: {output_path}")
    with open(output_file, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    print(f"Batch inference completed. Results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Prometheus 指标 AI 巡检推理脚本")
    parser.add_argument(
        "--model",
        type=str,
        default="Qwen/Qwen2.5-1.5B-Instruct",
        help="Base model path or HuggingFace model ID",
    )
    parser.add_argument(
        "--adapter-path",
        type=str,
        default="outputs/adapters",
        help="Path to LoRA adapter weights",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Path to input JSONL file for batch inference",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Path to output JSONL file for batch inference results",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Single prompt for one-off inference",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Maximum number of tokens to generate",
    )
    parser.add_argument(
        "--temp",
        type=float,
        default=0.1,
        help="Temperature for sampling (lower = more deterministic)",
    )
    parser.add_argument(
        "--no-adapter",
        action="store_true",
        help="Run base model without adapter for comparison",
    )

    args = parser.parse_args()

    # 验证参数
    if not args.prompt and not args.input:
        print("Error: Either --prompt or --input must be provided")
        parser.print_help()
        sys.exit(1)

    if args.input and not args.output:
        print("Error: --output must be provided when using --input")
        parser.print_help()
        sys.exit(1)

    # 加载模型
    adapter_path = None if args.no_adapter else args.adapter_path
    model, tokenizer = load_model(args.model, adapter_path)

    # 运行推理
    if args.prompt:
        single_inference(model, tokenizer, args.prompt, args.max_tokens, args.temp)
    else:
        batch_inference(
            model,
            tokenizer,
            args.input,
            args.output,
            args.max_tokens,
            args.temp,
        )


if __name__ == "__main__":
    main()
