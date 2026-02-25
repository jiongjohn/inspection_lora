# Prometheus 指标数据 AI 巡检 — 技术设计

> 版本: v0.1.0 | 日期: 2026-02-25

---

## 1. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 基座模型 | Qwen2.5-1.5B-Instruct | 中文强、数值推理好、1.5B 适配 M4 16GB |
| 训练框架 | MLX + mlx-lm | Apple Silicon 原生优化，LoRA 开箱支持 |
| 数据格式 | Alpaca JSON | instruction/input/output 三元组，工具链成熟 |
| 数据合成 | Claude API / GPT-4 API | 冷启动无标注数据，大模型合成是最优路径 |
| 配置管理 | YAML | 训练超参、LoRA 配置、数据路径统一管理 |
| Python | ≥ 3.11 | MLX 要求 |

---

## 2. LoRA 训练配置

```yaml
# configs/lora_config.yaml
model:
  name: Qwen/Qwen2.5-1.5B-Instruct
  quantization: 4bit          # MLX 4-bit 量化

lora:
  rank: 16                    # 1.5B 模型用 16 即可
  alpha: 32                   # 2x rank
  dropout: 0.05
  target_modules:             # Qwen2.5 架构
    - q_proj
    - k_proj
    - v_proj
    - o_proj
    - gate_proj
    - up_proj
    - down_proj

training:
  learning_rate: 2e-4
  lr_scheduler: cosine
  warmup_ratio: 0.03
  batch_size: 2               # M4 内存友好
  gradient_accumulation_steps: 8  # 有效 batch = 16
  max_seq_length: 2048
  epochs: 3
  seed: 42
```

---

## 3. 数据设计

### 3.1 输入格式（Prometheus 指标）
```
时间范围: {start_time} - {end_time}
实例: {instance}

{metric_name}{labels} {value}
{metric_name}{labels} {value}
...

历史基线({baseline_desc}):
{metric}: {baseline_value}
...
```

### 3.2 输出格式（巡检结果）
```markdown
## 巡检结果: {status_emoji} {status}

**异常发现:**
1. {metric} 当前值 {value}，较基线 {baseline} {direction} {percent}%，{severity}
...

**综合判断:** {analysis}

**建议:**
1. {action}
...
```

### 3.3 任务类型分布（目标 2000 条 MVP）

| 任务类型 | 占比 | 数量 | 说明 |
|---------|------|------|------|
| 单指标异常检测 | 25% | 500 | CPU/内存/磁盘/网络各类异常 |
| 多指标关联分析 | 20% | 400 | 跨指标根因推理 |
| 正常状态确认 | 20% | 400 | 避免过度报警 |
| 容量规划 | 15% | 300 | 趋势分析 + 阈值预警 |
| 健康评分 | 10% | 200 | 综合打分 0-100 |
| 巡检报告生成 | 10% | 200 | 完整结构化报告 |

---

## 4. 数据生成流水线

```
真实/模拟 Prometheus 指标
        │
        ▼
┌─────────────────────┐
│  指标模板引擎        │  参数化变异: 实例名、时间窗口、异常模式
│  data/templates/     │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  大模型合成          │  Claude/GPT-4 基于模板生成 instruction + output
│  generate_data.py    │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  质量过滤            │  格式校验 → 数值一致性 → 去重 → 长度过滤
│  filter_data.py      │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  数据集切分          │  train.jsonl / val.jsonl / test.jsonl
│  80% / 10% / 10%    │
└─────────────────────┘
```

---

## 5. 项目结构

```
inspection_lora/
├── openspec/                      # 项目规范文档
│   ├── requirements.md            # 需求定义
│   ├── design.md                  # 技术设计（本文档）
│   └── tasks.md                   # 任务拆解
├── configs/
│   ├── train_config.yaml          # 训练超参配置
│   └── lora_config.yaml           # LoRA 配置
├── data/
│   ├── templates/                 # 指标生成模板
│   │   ├── cpu_templates.py
│   │   ├── memory_templates.py
│   │   ├── disk_templates.py
│   │   ├── network_templates.py
│   │   └── composite_templates.py # 多指标组合模板
│   ├── generated/                 # 合成原始数据
│   └── processed/                 # 最终训练数据
│       ├── train.jsonl
│       ├── val.jsonl
│       └── test.jsonl
├── scripts/
│   ├── generate_data.py           # 数据合成入口
│   ├── filter_data.py             # 数据质量过滤
│   ├── split_data.py              # 数据集切分
│   ├── train.py                   # MLX LoRA 训练入口
│   ├── evaluate.py                # 评估脚本
│   ├── inference.py               # 推理脚本
│   └── merge_lora.py              # LoRA 权重合并
├── src/
│   └── inspection_lora/
│       ├── __init__.py
│       ├── metrics_parser.py      # Prometheus 指标解析器
│       ├── prompt_builder.py      # Prompt 构建器
│       └── data_utils.py          # 数据处理工具
├── outputs/                       # 训练输出（权重、日志）
├── requirements.txt
└── pyproject.toml
```

---

## 6. 评估指标

| 维度 | 指标 | MVP 目标 |
|------|------|----------|
| 异常检测 | Precision / Recall / F1 | F1 > 0.75 |
| 数值准确性 | 输出中引用数值与输入一致率 | > 90% |
| 根因推理 | 人工评估合理性 (1-5 分) | 平均 > 3.0 |
| 报告质量 | 结构完整性 + 可操作性 (1-5 分) | 平均 > 3.5 |
| 误报率 | 正常数据被判为异常的比例 | < 15% |
| 基座对比 | 微调后 vs 未微调 F1 提升 | > +0.2 |

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| M4 16GB 内存不足 | 训练 OOM | 降低 batch_size=1 + 增大 gradient_accumulation；或用 4-bit 量化 |
| 合成数据质量差 | 模型学到错误模式 | 人工抽检、多轮迭代模板、增加质量过滤规则 |
| 1.5B 模型能力不足 | 复杂推理效果差 | 先验证 MVP，不行则租云 GPU 训 3B/7B |
| MLX LoRA 对 Qwen2.5 支持不完善 | 训练报错 | 回退到 PyTorch MPS + PEFT 方案 |
| 大模型 API 成本 | 数据生成费用高 | 先用少量数据验证模板质量，再批量生成 |
