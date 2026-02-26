#!/usr/bin/env python3
"""
Prometheus 指标 AI 巡检评估脚本

功能：
- 异常检测 F1 分数（基于严重程度分类）
- 数值准确率（百分比值容差检查）
- 假阳性率（误报率）
- 结构完整性评分（必需章节检查）

用法：
    python scripts/evaluate.py \
        --predictions outputs/test_predictions.jsonl \
        --ground-truth data/processed/test.jsonl \
        --output outputs/eval_report.json
"""

import argparse
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Any


# MVP 阈值
MVP_THRESHOLDS = {
    "f1": 0.75,
    "accuracy": 0.90,
    "fpr": 0.15
}


def parse_severity(text: str) -> str:
    """
    从文本中解析严重程度
    
    返回: "critical", "warning", "normal"
    """
    if not text:
        return "normal"
    
    # 检查 emoji 指示器
    if "🔴" in text:
        return "critical"
    if "🟡" in text:
        return "warning"
    if "🟢" in text:
        return "normal"
    
    # 关键词检测
    text_lower = text.lower()
    
    critical_keywords = ["严重", "危急", "过高", "critical"]
    for kw in critical_keywords:
        if kw in text_lower:
            return "critical"
    
    warning_keywords = ["偏高", "偏低", "异常", "预警", "warning"]
    for kw in warning_keywords:
        if kw in text_lower:
            return "warning"
    
    normal_keywords = ["正常", "良好", "健康", "normal"]
    for kw in normal_keywords:
        if kw in text_lower:
            return "normal"
    
    # 默认为 normal
    return "normal"


def severity_to_binary(severity: str) -> str:
    """将严重程度转换为二分类：anomaly 或 normal"""
    return "anomaly" if severity in ["critical", "warning"] else "normal"


def extract_percentages(text: str) -> List[float]:
    """从文本中提取所有百分比数值"""
    if not text:
        return []
    
    pattern = r'(\d+\.?\d*)%'
    matches = re.findall(pattern, text)
    return [float(m) for m in matches]


def check_structural_completeness(text: str) -> Dict[str, float]:
    """
    检查生成文本的结构完整性
    
    返回每个部分的得分和总分
    """
    if not text:
        return {
            "has_severity": 0.0,
            "has_findings": 0.0,
            "has_analysis": 0.0,
            "has_recommendations": 0.0,
            "has_numbered_items": 0.0,
            "total": 0.0
        }
    
    scores = {}
    
    # 1. 严重程度指示器 (0.2)
    has_severity = bool(
        re.search(r'[🔴🟡🟢]', text) or 
        re.search(r'巡检结果', text, re.IGNORECASE)
    )
    scores["has_severity"] = 0.2 if has_severity else 0.0
    
    # 2. 发现章节 (0.2)
    has_findings = bool(
     re.search(r'异常发现|指标概览|指标详情', text, re.IGNORECASE)
    )
    scores["has_findings"] = 0.2 if has_findings else 0.0
    
    # 3. 分析章节 (0.2)
    has_analysis = bool(
        re.search(r'判断|分析', text, re.IGNORECASE)
    )
    scores["has_analysis"] = 0.2 if has_analysis else 0.0
    
    # 4. 建议章节 (0.2)
    has_recommendations = bool(
        re.search(r'建议', text, re.IGNORECASE)
    )
    scores["has_recommendations"] = 0.2 if has_recommendations else 0.0
    
    # 5. 编号列表 (0.2)
    has_numbered_items = bool(
        re.search(r'\d+\.\s+', text)
    )
    scores["has_numbered_items"] = 0.2 if has_numbered_items else 0.0
    
    scores["total"] = sum(scores.values())
    
    return scores


def compute_anomaly_detection_metrics(predictions: List[Dict]) -> Dict[str, float]:
    """
    计算异常检测的 precision, recall, F1
    
    二分类：anomaly (critical/warning) vs normal
    """
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    true_negatives = 0
    
    for pred in predictions:
        expected_text = pred.get("expected", "")
        generated_text = pred.get("generated", "")
        
        expected_severity = parse_severity(expected_text)
        generated_severity = parse_severity(generated_text)
        
        expected_binary = severity_to_binary(expected_severity)
        generated_binary = severity_to_binary(generated_severity)
        
        if expected_binary == "anomaly" and generated_binary == "anomaly":
            true_positives += 1
        elif expected_binary == "normal" and generated_binary == "anomaly":
            false_positives += 1
        elif expected_binary == "anomaly" and generated_binary == "normal":
            false_negatives += 1
        else:  # both normal
            true_negatives += 1
    
    # 计算指标
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "true_negatives": true_negatives
    }


def compute_numerical_accuracy(predictions: List[Dict], tolerance: float = 5.0) -> Dict[str, Any]:
    """
    计算数值准确率
    
    检查生成文本中的百分比值是否在容差范围内（默认 ±5%）
    """
    total_expected_values = 0
    matched_values = 0
    
    for pred in predictions:
        expected_text = pred.get("expected", "")
        generated_text = pred.get("generated", "")
        
        expected_percentages = extract_percentages(expected_text)
        generated_percentages = extract_percentages(generated_text)
        
        # 对每个期望值，检查是否有生成值在容差范围内
        for exp_val in expected_percentages:
            total_expected_values += 1
            
            # 检查是否有任何生成值在容差范围内
            for gen_val in generated_percentages:
                if abs(exp_val - gen_val) <= tolerance:
                    matched_values += 1
                    break  # 找到匹配就跳出
    
    accuracy = matched_values / total_expected_values if total_expected_values > 0 else 0.0
    
    return {
        "matched": matched_values,
        "total": total_expected_values,
        "accuracy": round(accuracy, 4)
    }


def compute_false_positive_rate(predictions: List[Dict]) -> Dict[str, Any]:
    """
    计算假阳    
    FPR = 误报数 / 实际正常样本数
    """
    total_normal_cases = 0
    false_positives = 0
    
    for pred in predictions:
        expected_text = pred.get("expected", "")
        generated_text = pred.get("generated", "")
        
        expected_severity = parse_severity(expected_text)
        generated_severity = parse_severity(generated_text)
        
        expected_binary = severity_to_binary(expected_severity)
        generated_binary = severity_to_binary(generated_severity)
        
        if expected_binary == "normal":
            total_normal_cases += 1
            if generated_binary == "anomaly":
                false_positives += 1
    
    fpr = false_positives / total_normal_cases if total_normal_cases > 0 else 0.0
    
    return {
        "false_positives": false_positives,
        "total_normal": total_normal_cases,
        "fpr": round(fpr, 4)
    }


def compute_structural_completeness(predictions: List[Dict]) -> Dict[str, Any]:
    """
    计算结构完整性平均分
    """
    all_scores = []
    section_totals = defaultdict(float)
    
    for pred in predictions:
        generated_text = pred.get("generated", "")
        scores = check_structural_completeness(generated_text)
        
        all_scores.append(scores["total"])
        
        for key, value in scores.items():
            if key != "total":
                section_totals[key] += value
    
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
    
    # 计算每个部分的平均分
    per_section = {}
    num_samples = len(predictions)
    if num_samples > 0:
        for key, total in section_totals.items():
            per_section[key] = round(total / num_samples, 4)
    
    return {
        "avg_score": round(avg_score, 4),
        "per_section": per_section
    }


def load_predictions(predictions_path: Path) -> List[Dict]:
    """加载预测结果 JSONL 文件"""
    predictions = []
    
    if not predictions_path.exists():
        raise FileNotFoundError(f"预测文件不存在: {predictions_path}")
    
    with open(predictions_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                pred = json.loads(line)
                predictions.append(pred)
            except json.JSONDecodeError as e:
                print(f"警告: 第 {line_num} 行 JSON 解析失败: {e}")
                continue
    
    return predictions


def evaluate(predictions_path: Path, ground_truth_path: Path, output_path: Path):
    """
    主评估函数
    """
    print(f"正在加载预测结果: {predictions_path}")
    predictions = load_predictions(predictions_path)
    
    if not predictions:
        print("错误: 没有找到有效的预测数据")
        return
    
    print(f"已加载 {len(predictions)} 条预测结果")
    
    # 计算各项指标
    print("\n正在计算评估指标...")
    
    anomaly_metrics = compute_anomaly_detection_metrics(predictions)
    numerical_metrics = compute_numerical_accuracy(predictions)
    fpr_metrics = compute_false_positive_rate(predictions)
    structural_metrics = compute_structural_completeness(predictions)
    
    # MVP 通过检查
    mvp_pass = {
        "f1_pass": anomaly_metrics["f1"] >= MVP_THRESHOLDS["f1"],
        "accuracy_pass": numerical_metrics["accuracy"] >= MVP_THRESHOLDS["accuracy"],
        "fpr_pass": fpr_metrics["fpr"] <= MVP_THRESHOLDS["fpr"],
    }
    mvp_pass["all_pass"] = all(mvp_pass.values())
    
    # 构建报告
    report = {
        "total_samples": len(predictions),
        "anomaly_detection": anomaly_metrics,
        "numerical_accuracy": numerical_metrics,
        "structural_completeness": structural_metrics,
        "mvp_pass": mvp_pass,
        "mvp_thresholds": MVP_THRESHOLDS
    }
    
    # 保存 JSON 报告
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n评估报告已保存至: {output_path}")
    
    # 打印人类可读摘要
    print("\n" + "=" * 60)
    print("评估结果摘要")
    print("=" * 60)
    print(f"\n总样本数: {len(predictions)}")
    
    print(f"\n【异常检测】")
    print(f"  Precision: {anomaly_metrics['precision']:.2%}")
    print(f"  Recall:    {anomaly_metrics['recall']:.2%}")
    print(f"  F1 Score:  {anomaly_metrics['f1']:.2%} {'✓' if mvp_pass['f1_pass'] else '✗ (需要 ≥ 75%)'}")
    
    print(f"\n【数值准确率】")
    print(f"  匹配数/总数: {numerical_metrics['matched']}/{numerical_metrics['total']}")
    print(f"  准确率:      {numerical_metrics['accuracy']:.2%} {'✓' if mvp_pass['accuracy_pass'] else '✗ (需要 ≥ 90%)'}")
    
    print(f"\n【假阳性率】")
    print(f"  误报数/正常样本数: {fpr_metrics['false_positives']}/{fpr_metrics['total_normal']}")
    print(f"  FPR:              {fpr_metrics['fpr']:.2%} {'✓' if mvp_pass['fpr_pass'] else '✗ (需要 ≤ 15%)'}")
    
    print(f"\n【结构完整性】")
    print(f"  平均得分: {structural_metrics['avg_score']:.2%}")
    for section, score in structural_metrics['per_section'].items():
        section_name = {
            "has_severity": "严重程度指示器",
            "has_findings": "发现章节",
            "has_analysis": "分析章节",
            "has_recommendations": "建议章节",
            "has_numbered_items": "编号列表"
        }.get(section, section)
        print(f"    {section_name}: {score:.2%}")
    
    print(f"\n{'=' * 60}")
    if mvp_pass["all_pass"]:
        print("🎉 MVP 标准全部通过！")
    else:
        print("⚠️  部分指标未达到 MVP 标准")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Prometheus 指标 AI 巡检评估脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="预测结果 JSONL 文件路径 (inference.py 输出)"
    )
    
    parser.add_argument(
        "--ground-truth",
        type=Path,
        required=True,
        help="真实标签 JSONL 文件路径 (data/processed/test.jsonl)"
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/eval_report.json"),
        help="评估报告输出路径 (默认: outputs/eval_report.json)"
    )
    
    args = parser.parse_args()
    
    evaluate(args.predictions, args.ground_truth, args.output)


if __name__ == "__main__":
    main()
