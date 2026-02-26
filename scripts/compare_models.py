"""
模型对比脚本

比较基座模型和微调模型的评估结果，计算各项指标的变化量。
用于验证微调效果是否达到预期（F1 提升 > +0.2）。
"""

import json
import argparse
from pathlib import Path


def load_report(path: Path) -> dict:
    """加载评估报告 JSON 文件"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_fpr(report: dict) -> float:
    """从 anomaly_detection 计算 FPR"""
    ad = report["anomaly_detection"]
    fp = ad.get("false_positives", 0)
    tn = ad.get("true_negatives", 0)
    return fp / (fp + tn) if (fp + tn) > 0 else 0.0


def compute_deltas(base: dict, finetuned: dict) -> dict:
    """计算指标变化量"""
    deltas = {
        "f1": finetuned["anomaly_detection"]["f1"] - base["anomaly_detection"]["f1"],
        "accuracy": finetuned["numerical_accuracy"]["accuracy"]
        - base["numerical_accuracy"]["accuracy"],
        "fpr": _get_fpr(finetuned) - _get_fpr(base),
        "structural_completeness": finetuned["structural_completeness"]["avg_score"]
        - base["structural_completeness"]["avg_score"],
    }
    return deltas


def print_comparison(base: dict, finetuned: dict, deltas: dict, f1_pass: bool):
    """打印中文对比报告"""
    print("\n=== 模型对比报告 ===")
    print(f"{'指标':<20} {'基座模型':<12} {'微调模型':<12} {'变化':<12}")
    print("-" * 60)

    # 异常检测 F1
    f1_base = base["anomaly_detection"]["f1"]
    f1_ft = finetuned["anomaly_detection"]["f1"]
    f1_delta = deltas["f1"]
    f1_icon = "✅" if f1_delta > 0 else "❌"
    print(f"{'异常检测 F1:':<20} {f1_base:<12.4f} {f1_ft:<12.4f} {f1_delta:+.4f} {f1_icon}")

    # 数值准确率
    acc_base = base["numerical_accuracy"]["accuracy"]
    acc_ft = finetuned["numerical_accuracy"]["accuracy"]
    acc_delta = deltas["accuracy"]
    acc_icon = "✅" if acc_delta > 0 else "❌"
    print(f"{'数值准确率:':<20} {acc_base:<12.4f} {acc_ft:<12.4f} {acc_delta:+.4f} {acc_icon}")

    # 误报率
    fpr_base = _get_fpr(base)
    fpr_ft = _get_fpr(finetuned)
    fpr_delta = deltas["fpr"]
    fpr_icon = "✅" if fpr_delta < 0 else "❌"
    print(f"{'误报率:':<20} {fpr_base:<12.4f} {fpr_ft:<12.4f} {fpr_delta:+.4f} {fpr_icon}")

    # 结构完整性
    struct_base = base["structural_completeness"]["avg_score"]
    struct_ft = finetuned["structural_completeness"]["avg_score"]
    struct_delta = deltas["structural_completeness"]
    struct_icon = "✅" if struct_delta > 0 else "❌"
    print(
        f"{'结构完整性:':<20} {struct_base:<12.4f} {struct_ft:<12.4f} {struct_delta:+.4f} {struct_icon}"
    )

    print("\n" + "-" * 60)
    pass_text = "✅ 通过" if f1_pass else "❌ 未通过"
    print(f"F1 提升 > +0.2: {pass_text}")
    print()


def main():
    parser = argparse.ArgumentParser(description="比较基座模型和微调模型的评估结果")
    parser.add_argument(
        "--base-report",
        type=str,
        default="outputs/eval_report_base.json",
        help="基座模型评估报告路径",
    )
    parser.add_argument(
        "--finetuned-report",
        type=str,
        default="outputs/eval_report.json",
        help="微调模型评估报告路径",
    )
    parser.add_argument(
        "--output", type=str, default="outputs/comparison_report.json", help="对比报告输出路径"
    )

    args = parser.parse_args()

    # 加载报告
    base_path = Path(args.base_report)
    finetuned_path = Path(args.finetuned_report)

    if not base_path.exists():
        raise FileNotFoundError(f"基座模型报告不存在: {base_path}")
    if not finetuned_path.exists():
        raise FileNotFoundError(f"微调模型报告不存在: {finetuned_path}")

    base_report = load_report(base_path)
    finetuned_report = load_report(finetuned_path)

    # 计算变化量
    deltas = compute_deltas(base_report, finetuned_report)

    # 检查 F1 提升是否达标
    f1_threshold = 0.2
    f1_improvement_pass = deltas["f1"] > f1_threshold

    # 构建对比报告
    comparison_report = {
        "base_model": base_report,
        "finetuned_model": finetuned_report,
        "deltas": deltas,
        "f1_improvement_pass": f1_improvement_pass,
        "f1_improvement_threshold": f1_threshold,
    }

    # 保存对比报告
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(comparison_report, f, indent=2, ensure_ascii=False)

    print(f"对比报告已保存至: {output_path}")

    # 打印对比结果
    print_comparison(base_report, finetuned_report, deltas, f1_improvement_pass)


if __name__ == "__main__":
    main()
