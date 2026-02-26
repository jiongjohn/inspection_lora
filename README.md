# Inspection LoRA

Prometheus 指标数据 AI 巡检 — 基于 LoRA 微调的智能运维巡检模型。

本项目通过对 Qwen2.5-1.5B-Instruct 模型进行 LoRA 微调，使其能够自动分析 Prometheus 监控指标数据，生成结构化的中文巡检报告，包括异常检测、根因分析和处置建议。

## 核心能力

- **异常检测**: 识别 CPU、内存、磁盘、网络等指标的单指标/多指标异常
- **健康评估**: 对节点进行综合健康评分
- **容量预测**: 基于当前趋势进行容量规划分析
- **巡检报告**: 生成包含发现、分析、建议的结构化中文报告

## 支持的巡检场景

| 场景类型 | 说明 | 模板数量 |
|---------|------|---------|
| single_anomaly | 单指标异常检测 | 15 |
| multi_metric | 多指标关联异常 | 6 |
| normal | 正常状态确认 | 4 |
| capacity | 容量规划分析 | 3 |
| health | 节点健康评估 | 6 |
| report | 综合巡检报告 | 6 |

## 技术栈

- **基座模型**: Qwen/Qwen2.5-1.5B-Instruct
- **微调框架**: [MLX](https://github.com/ml-explore/mlx) + [MLX-LM](https://github.com/ml-explore/mlx-examples) (Apple Silicon 原生)
- **微调方法**: LoRA (rank=16, alpha=32, dropout=0.05)
- **目标层**: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj
- **Python**: >= 3.11

## 项目结构

```
inspection_lora/
├── configs/                    # 训练与评估配置
│   ├── lora_config.yaml        # LoRA 训练配置 (rank=16)
│   ├── lora_config_rank8.yaml  # rank=8 对比实验
│   ├── lora_config_rank32.yaml # rank=32 对比实验
│   └── eval_config.yaml        # 评估配置
├── data/
│   ├── templates/              # 数据生成模板引擎
│   │   ├── cpu_templates.py
│   │   ├── memory_templates.py
│   │   ├── disk_templates.py
│   │   ├── network_templates.py
│   │   └── composite_templates.py
│   ├── generated/              # 生成的原始数据 (gitignored)
│   └── processed/              # 处理后的训练/测试数据 (gitignored)
├── scripts/
│   ├── generate_data.py        # 合成训练数据
│   ├── filter_data.py          # 数据过滤清洗
│   ├── split_data.py           # 训练/测试集划分
│   ├── inference.py            # 模型推理
│   ├── evaluate.py             # 模型评估
│   ├── compare_models.py       # 多模型对比
│   └── e2e_test.py             # 端到端测试
├── src/inspection_lora/        # 核心库
│   ├── data_utils.py           # 数据结构与工具函数
│   ├── prompt_builder.py       # Prompt 构建器
│   └── metrics_parser.py       # 指标解析器
├── outputs/                    # 训练产物 (gitignored)
│   └── adapters/               # LoRA adapter 权重
├── init.sh                     # 环境初始化脚本
├── pyproject.toml
└── requirements.txt
```

## 快速开始

### 1. 环境初始化

```bash
# 自动检查 Python 版本、创建虚拟环境、验证依赖
bash init.sh
```

或手动安装:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. 生成训练数据

```bash
python scripts/generate_data.py
```

数据分布: single_anomaly 25% / multi_metric 20% / normal 20% / capacity 15% / health 10% / report 10%

### 3. 数据处理

```bash
# 过滤清洗
python scripts/filter_data.py

# 划分训练集/测试集
python scripts/split_data.py
```

### 4. LoRA 微调

使用 mlx-lm 进行训练:

```bash
mlx_lm.lora --config configs/lora_config.yaml
```

训练参数:
- Batch size: 2, Gradient accumulation: 8 (有效 batch=16)
- Learning rate: 2e-4, Cosine decay, Warmup: 50 steps
- 总迭代: 1000, 每 200 步保存 checkpoint
- 最大序列长度: 2048

### 5. 推理

```bash
python scripts/inference.py
```

支持加载 LoRA adapter 进行单条或批量推理。

### 6. 评估

```bash
python scripts/evaluate.py
```

评估指标:
- **异常检测 F1**: 衡量异常识别的准确率和召回率
- **数值准确率**: 指标数值的解析精度
- **误报率 (FPR)**: 正常场景被误判为异常的比例
- **结构完整性**: 输出报告的格式规范程度

MVP 达标线: F1 > 0.75 / 准确率 > 90% / 误报率 < 15%

## 超参数对比

项目提供了 rank=8/16/32 三组配置用于对比实验:

```bash
# rank=8
mlx_lm.lora --config configs/lora_config_rank8.yaml

# rank=16 (默认)
mlx_lm.lora --config configs/lora_config.yaml

# rank=32
mlx_lm.lora --config configs/lora_config_rank32.yaml

# 对比评估
python scripts/compare_models.py
```

## 依赖

| 包 | 版本 | 用途 |
|---|------|------|
| mlx | >= 0.22 | Apple Silicon ML 框架 |
| mlx-lm | >= 0.22 | LLM 训练/推理工具 |
| transformers | >= 4.45 | Tokenizer & 模型加载 |
| datasets | >= 3.0 | 数据集处理 |
| numpy | >= 1.26 | 数值计算 |
| huggingface-hub | >= 0.25 | 模型下载 |
| pyyaml | >= 6.0 | 配置文件解析 |
| jsonlines | >= 4.0 | JSONL 数据读写 |

> 注意: 本项目基于 MLX 框架，仅支持 Apple Silicon (M1/M2/M3/M4) Mac。

## License

MIT
