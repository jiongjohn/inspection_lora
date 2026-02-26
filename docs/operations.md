# Inspection LoRA — 完整操作手册

> 项目: Prometheus 指标数据 AI 巡检 LoRA 微调
> 模型: Qwen2.5-1.5B-Instruct + MLX LoRA
> 更新: 2026-02-26

---

## 0. 环境准备

```bash
# 激活虚拟环境
source .venv/bin/activate

# 验证依赖
python -c "
import mlx.core, mlx_lm, transformers, datasets, yaml, jsonlines, numpy
print('所有依赖已就绪')
"
```

---

## 1. 模型下载 (F-1.4)

首次运行需要下载 ~3GB，后续会使用缓存。

```bash
# 方式一：通过 mlx_lm 自动下载 + 验证加载（推荐）
python -c "
from mlx_lm import load
m, t = load('Qwen/Qwen2.5-1.5B-Instruct')
print('模型下载并加载成功')
"

# 方式二：仅下载不加载
# python -c "
# from huggingface_hub import snapshot_download
# snapshot_download('Qwen/Qwen2.5-1.5B-Instruct')
# print('下载完成')
# "
```

---

## 2. 训练数据生成 (F-2.1 ~ F-2.9)

从模板引擎合成训练数据，经过质量过滤后切分为 train/valid/test。

### 2a. 生成原始数据

```bash
python scripts/generate_data.py --count 2200 --seed 42
```

**输出:** `data/generated/raw_data.jsonl` (2200 条原始样本)

### 2b. 质量过滤

```bash
python scripts/filter_data.py \
  --input data/generated/raw_data.jsonl \
  --output data/generated/filtered_data.jsonl
```

**输出:** `data/generated/filtered_data.jsonl` (过滤后约 2200 条)

### 2c. 数据集切分 (80/10/10)

```bash
python scripts/split_data.py \
  --input data/generated/filtered_data.jsonl \
  --output-dir data/processed \
  --seed 42
```

**输出:**
- `data/processed/train.jsonl` (1760 条)
- `data/processed/valid.jsonl` (220 条)
- `data/processed/test.jsonl` (220 条)

---

## 3. Dummy 训练验证 (F-1.6)

生成少量测试数据，验证训练 pipeline 可跑通。预计耗时: 2-5 分钟。

```bash
python scripts/create_dummy_data.py
python -m mlx_lm lora --config configs/lora_config_dummy.yaml
```

**验证:** `outputs/adapters_dummy/` 目录下应有 `adapters.safetensors`

---

## 4. 正式训练 (F-3.1 / F-3.2 / F-3.3)

使用完整数据集 (1760 train / 220 valid) 训练 1000 步。

- 配置: rank=16, batch=2, grad_accum=8, lr=2e-4, cosine decay
- 预计耗时: 30-60 分钟
- 预期结果: train loss ~0.1, val loss ~0.1

```bash
python -m mlx_lm lora --config configs/lora_config.yaml
```

**验证:**
- `outputs/adapters/adapters.safetensors` 存在
- 训练日志中 loss 持续下降并收敛

---

## 5. 合并 LoRA 权重 (F-3.4)

将 LoRA adapter 合并回基座模型，生成独立可部署的模型。预计耗时: ~1 分钟。

```bash
python -m mlx_lm fuse \
  --model Qwen/Qwen2.5-1.5B-Instruct \
  --adapter-path outputs/adapters \
  --save-path outputs/fused_model
```

**验证:** `outputs/fused_model/` 目录下有完整模型文件

---

## 6. 推理 + 评估 (F-4.1 / F-4.2 / F-4.3)

### 6a. 微调模型推理 test 集

预计耗时: 10-20 分钟 (220 条样本)

```bash
python scripts/inference.py \
  --input data/processed/test.jsonl \
  --output outputs/test_predictions.jsonl
```

### 6b. 评估

```bash
python scripts/evaluate.py \
  --predictions outputs/test_predictions.jsonl \
  --ground-truth data/processed/test.jsonl \
  --output outputs/eval_report.json
```

**MVP 标准:**
- 异常检测 F1 > 75%
- 数值准确率 > 90%
- 假阳性率 < 15%

---

## 7. 基座模型对比 (F-4.4)

### 7a. 基座模型推理（无 adapter）

预计耗时: 10-20 分钟

```bash
python scripts/inference.py \
  --no-adapter \
  --input data/processed/test.jsonl \
  --output outputs/base_predictions.jsonl
```

### 7b. 基座模型评估

```bash
python scripts/evaluate.py \
  --predictions outputs/base_predictions.jsonl \
  --ground-truth data/processed/test.jsonl \
  --output outputs/eval_report_base.json
```

### 7c. 对比报告

```bash
python scripts/compare_models.py \
  --base-report outputs/eval_report_base.json \
  --finetuned-report outputs/eval_report.json \
  --output outputs/comparison_report.json
```

**验证:** F1 提升 > +0.2

---

## 8. 端到端测试 (F-4.5)

10 个真实场景端到端验证。预计耗时: 5-10 分钟。

```bash
python scripts/e2e_test.py \
  --model Qwen/Qwen2.5-1.5B-Instruct \
  --adapter-path outputs/adapters \
  --output outputs/e2e_results.json
```

**通过标准:** 平均评分 > 3.0/5.0

---

## 9. 超参调优 (F-3.5)

3 组实验: rank 8 / 16 / 32。rank=16 已在 Step 4 完成，只需额外跑 rank=8 和 rank=32。

预计耗时: 每组 30-60 分钟，共 1-2 小时。

```bash
# rank=8 实验
python -m mlx_lm lora --config configs/lora_config_rank8.yaml

# rank=32 实验
python -m mlx_lm lora --config configs/lora_config_rank32.yaml
```

对比三组实验 loss 曲线，选择最优 rank。

---

## 附录: 单条推理测试

快速测试模型效果（使用 adapter）：

```bash
python scripts/inference.py \
  --prompt "时间范围: 2026-02-25 14:00 - 2026-02-25 15:00
实例: node-web-01:9100

node_cpu_seconds_total{cpu=\"0\",mode=\"user\"} 92.5
node_cpu_seconds_total{cpu=\"0\",mode=\"system\"} 5.3
node_cpu_seconds_total{cpu=\"0\",mode=\"idle\"} 2.2

基线数据 (过去7天平均):
node_cpu_seconds_total{mode=\"user\"}: 35.0
node_cpu_seconds_total{mode=\"system\"}: 8.0
node_cpu_seconds_total{mode=\"idle\"}: 57.0"
```
