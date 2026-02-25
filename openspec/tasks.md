# Prometheus 指标数据 AI 巡检 — 任务拆解

> 版本: v0.1.0 | 日期: 2026-02-25

---

## Phase 1 — 环境与基础设施 (US-1)

- [ ] T-1.1: 初始化项目目录结构
- [ ] T-1.2: 创建 pyproject.toml / requirements.txt，锁定依赖版本
  - mlx >= 0.22, mlx-lm >= 0.22, transformers, datasets, pyyaml, jsonlines
- [ ] T-1.3: 创建 Python 虚拟环境，安装依赖
- [ ] T-1.4: 下载 Qwen2.5-1.5B-Instruct 模型，验证加载成功
- [ ] T-1.5: 创建 configs/lora_config.yaml 和 configs/train_config.yaml
- [ ] T-1.6: 验证 MLX LoRA 训练 pipeline 可跑通（用 10 条 dummy 数据）

**里程碑 M1:** 环境就绪，dummy 训练跑通 | 预估 1-2 天

---

## Phase 2 — 数据生成 (US-2)

- [ ] T-2.1: 实现 Prometheus 指标解析器 `src/inspection_lora/metrics_parser.py`
- [ ] T-2.2: 实现 Prompt 构建器 `src/inspection_lora/prompt_builder.py`
- [ ] T-2.3: 编写指标模板引擎
  - [ ] T-2.3.1: CPU 指标模板 (正常 + 5 种异常模式)
  - [ ] T-2.3.2: 内存指标模板 (正常 + 4 种异常模式)
  - [ ] T-2.3.3: 磁盘指标模板 (正常 + 4 种异常模式)
  - [ ] T-2.3.4: 网络指标模板 (正常 + 3 种异常模式)
  - [ ] T-2.3.5: 多指标组合模板 (6 种关联场景)
- [ ] T-2.4: 实现数据合成脚本 `scripts/generate_data.py`
  - 调用 Claude/GPT-4 API 基于模板生成 instruction-tuning 数据
  - 支持断点续传、并发请求、进度显示
- [ ] T-2.5: 实现数据质量过滤 `scripts/filter_data.py`
  - JSON 格式校验、字段完整性、数值一致性、去重、长度过滤
- [ ] T-2.6: 实现数据集切分 `scripts/split_data.py` (80/10/10)
- [ ] T-2.7: 生成 MVP 数据集 (≥ 2000 条)，人工抽检 50 条确认质量

**里程碑 M2:** 2000 条训练数据就绪 | 预估 3-5 天

---

## Phase 3 — 训练 (US-6)

- [ ] T-3.1: 实现 MLX LoRA 训练脚本 `scripts/train.py`
  - 读取 YAML 配置、加载模型、应用 LoRA、训练循环、保存权重
- [ ] T-3.2: 实现数据加载器（JSONL → MLX 训练格式）
- [ ] T-3.3: 用 MVP 数据集完成首次训练，确认 loss 收敛
- [ ] T-3.4: 实现 LoRA 权重合并脚本 `scripts/merge_lora.py`
- [ ] T-3.5: 超参调优（至少 3 组实验：rank 8/16/32）

**里程碑 M3:** 首次训练完成，loss 收敛 | 预估 1 天

---

## Phase 4 — 推理与评估 (US-3, US-4, US-5, US-7)

- [ ] T-4.1: 实现推理脚本 `scripts/inference.py`
  - 加载 LoRA 权重、构建 prompt、生成回答、解析输出
- [ ] T-4.2: 实现评估脚本 `scripts/evaluate.py`
  - 异常检测 F1、数值准确率、结构完整性评分
- [ ] T-4.3: 在 test 集上运行评估，生成评估报告
- [ ] T-4.4: 基座模型 vs 微调模型对比评估
- [ ] T-4.5: 端到端测试：手工构造 10 个真实场景，验证模型输出质量

**里程碑 M4:** 评估完成，达到 MVP 指标 | 预估 1-2 天

---

## 依赖关系

```
Phase 1 ──▶ Phase 2 ──▶ Phase 3 ──▶ Phase 4
  (环境)      (数据)      (训练)      (评估)

T-1.6 ──▶ T-2.1 (环境就绪后才能开发数据工具)
T-2.7 ──▶ T-3.3 (数据就绪后才能正式训练)
T-3.3 ──▶ T-4.1 (训练完成后才能推理评估)

可并行:
  T-2.1 ~ T-2.3 (解析器、构建器、模板引擎可并行开发)
  T-4.1 ~ T-4.2 (推理和评估脚本可并行开发)
```

---

## 总预估

| 阶段 | 时间 |
|------|------|
| Phase 1 | 1-2 天 |
| Phase 2 | 3-5 天 |
| Phase 3 | 1 天 |
| Phase 4 | 1-2 天 |
| **合计** | **6-10 天** |
