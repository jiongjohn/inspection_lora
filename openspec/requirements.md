# Prometheus 指标数据 AI 巡检 — LoRA 微调项目需求

> 版本: v0.1.0 | 日期: 2026-02-25 | 状态: Draft

---

## 1. 项目概述

基于 Qwen2.5-1.5B-Instruct 小模型，通过 MLX + LoRA 微调，训练一个专用于 Prometheus 指标数据分析的 AI 巡检模型。在 Apple M4 芯片上本地完成训练与推理。

**核心能力:** 异常检测 · 根因分析 · 容量规划 · 巡检报告生成

---

## 2. 用户故事

### US-1: 项目环境搭建
作为开发者，我需要一个完整的 MLX + LoRA 训练环境，以便在 Apple M4 芯片上本地训练模型。

**验收标准:**
- [ ] Python 虚拟环境创建成功，依赖安装无报错
- [ ] MLX、mlx-lm、transformers 等核心依赖版本锁定
- [ ] 能成功加载 Qwen2.5-1.5B-Instruct 基座模型
- [ ] 项目目录结构符合规范

### US-2: 训练数据生成
作为开发者，我需要一套自动化的训练数据生成流水线，能够批量产出高质量的 Prometheus 指标分析 instruction-tuning 数据。

**验收标准:**
- [ ] Prometheus 指标模板引擎：支持参数化生成不同场景的指标数据
- [ ] 大模型合成脚本：调用 Claude/GPT-4 API 基于模板生成 instruction/input/output 三元组
- [ ] 数据质量过滤：格式校验、数值一致性检查、去重
- [ ] 最终产出 ≥ 2000 条训练数据（Alpaca JSON 格式）
- [ ] 数据集按 80/10/10 切分为 train/val/test

### US-3: 指标异常检测
作为运维工程师，我输入一组 Prometheus 指标数据，模型能识别出异常指标并给出异常描述。

**验收标准:**
- [ ] 支持 node_exporter 常见指标（CPU、内存、磁盘、网络、负载）
- [ ] 能识别突增、突降、持续偏高、周期性异常等模式
- [ ] 输出包含：异常指标名、当前值、基线值、偏离幅度、严重程度
- [ ] 正常数据能正确判定为"无异常"（误报率 < 15%）

### US-4: 多指标关联分析
作为运维工程师，我输入多个相关指标，模型能关联分析并推断可能的根因。

**验收标准:**
- [ ] 支持跨指标关联（如 CPU system 高 + iowait 高 → 磁盘 I/O 瓶颈）
- [ ] 输出包含：关联关系描述、根因推断、置信度
- [ ] 能给出下一步排查建议

### US-5: 巡检报告生成
作为运维工程师，我输入一批指标数据，模型能生成结构化的中文巡检报告。

**验收标准:**
- [ ] 报告包含：概览、异常发现、健康评分(0-100)、建议措施
- [ ] 中文输出，Markdown 格式规范
- [ ] 引用的数值与输入数据一致

### US-6: LoRA 训练流程
作为开发者，我需要一键启动 LoRA 训练，并能监控训练过程和评估结果。

**验收标准:**
- [ ] 训练脚本支持 MLX 后端，M4 芯片可运行
- [ ] 支持 YAML 配置文件驱动，无需改代码调参
- [ ] 训练过程输出 loss 曲线
- [ ] 训练完成后自动在 val 集上评估
- [ ] LoRA 权重可保存、加载、合并到基座模型

### US-7: 推理与评估
作为开发者，我需要评估微调后模型的效果，并提供推理接口。

**验收标准:**
- [ ] 评估脚本：在 test 集上计算异常检测 F1、数值准确率、报告质量评分
- [ ] 推理脚本：支持单条/批量输入，输出结构化结果
- [ ] 与基座模型（未微调）的对比评估报告

---

## 3. 非功能需求

| ID | 需求 | 指标 |
|----|------|------|
| NFR-1 | 硬件兼容 | Apple M4 16GB 可完成训练 |
| NFR-2 | 训练时间 | ≤ 3 小时 / 2000 条数据 |
| NFR-3 | 可复现性 | 随机种子固定，依赖版本锁定 |
| NFR-4 | 可扩展性 | 支持切换 3B/7B 模型，模板易扩展 |

---

## 4. 指标覆盖范围

### 第一期（MVP）
```
node_cpu_seconds_total          # CPU 各模式耗时
node_memory_MemAvailable_bytes  # 可用内存
node_memory_MemTotal_bytes      # 总内存
node_filesystem_avail_bytes     # 磁盘可用空间
node_filesystem_size_bytes      # 磁盘总空间
node_disk_io_time_seconds_total # 磁盘 I/O 时间
node_network_receive_bytes_total  # 网络接收
node_network_transmit_bytes_total # 网络发送
node_load1 / node_load5 / node_load15 # 系统负载
```

### 第二期（扩展）
```
container_cpu_usage_seconds_total       # 容器 CPU
container_memory_working_set_bytes      # 容器内存
http_requests_total                     # HTTP 请求量
http_request_duration_seconds_bucket    # 请求延迟分布
```
