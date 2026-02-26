#!/usr/bin/env python3
"""生成用于验证 MLX LoRA 训练管道的虚拟数据"""

import json
from pathlib import Path

# 系统提示词
SYSTEM_PROMPT = "你是一个专业的基础设施监控助手，负责分析 Prometheus 指标数据。"

# 创建10个多样化的样本
samples = [
    # 1. CPU异常
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "node_cpu_seconds_total: 当前95.2%, 基线70%. node_load1: 8.5, 基线3.2",
            },
            {
                "role": "assistant",
                "content": "🔴 CPU异常告警\n1. CPU使用率95.2%，超出基线25.2%\n2. 系统负载8.5，超出基线165%\n判断：CPU资源严重不足\n建议：\n1. 排查高负载进程\n2. 考虑扩容",
            },
        ]
    },
    # 2. 内存危急
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "node_memory_MemAvailable_bytes: 512MB, 总量32GB, 可用率1.6%, 基线可用率25%",
            },
            {
                "role": "assistant",
                "content": "🔴 内存危急告警\n1. 可用内存仅512MB，可用率1.6%\n2. 远低于基线25%，偏离23.4%\n判断：内存即将耗尽\n建议：\n1. 立即释放内存\n2. 重启高内存进程\n3. 紧急扩容",
            },
        ]
    },
    # 3. 磁盘正常
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "node_filesystem_avail_bytes: 450GB, 总量500GB, 使用率10%, 基线12%",
            },
            {
                "role": "assistant",
                "content": "🟢 磁盘状态正常\n1. 可用空间450GB，使用率10%\n2. 低于基线12%，状态良好\n判断：磁盘空间充足\n建议：\n1. 保持当前监控策略",
            },
        ]
    },
    # 4. 网络异常
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "node_network_receive_bytes_total: 850MB/s, 基线200MB/s, 发送: 920MB/s, 基线180MB/s",
            },
            {
                "role": "assistant",
                "content": "🟡 网络流量异常\n1. 接收流量850MB/s，超基线325%\n2. 发送流量920MB/s，超基线411%\n判断：网络流量激增\n建议：\n1. 检查异常流量来源\n2. 确认是否遭受攻击\n3. 评估带宽扩容",
            },
        ]
    },
    # 5. 负载异常
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "node_load1: 12.8, node_load5: 10.2, node_load15: 8.5, CPU核心数: 4, 基线load1: 2.0",
            },
            {
                "role": "assistant",
                "content": "🔴 系统负载过高\n1. 1分钟负载12.8，为核心数的320%\n2. 超出基线2.0达540%\n判断：系统严重过载\n建议：\n1. 立即定位高负载任务\n2. 终止非关键进程\n3. 增加计算资源",
            },
        ]
    },
    # 6. 多指标关联
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "node_cpu_seconds_total: 88%, node_memory_MemAvailable_bytes: 2GB/32GB, node_disk_io_time_seconds_total: 0.95, 基线CPU: 60%, 基线内存可用: 40%, 基线IO: 0.3",
            },
            {
                "role": "assistant",
                "content": "🟡 多指标异常关联\n1. CPU 88%超基线28%\n2. 内存可用率6.25%低于基线33.75%\n3. 磁盘IO 0.95超基线217%\n判断：资源竞争导致性能下降\n建议：\n1. 优化IO密集任务\n2. 增加内存缓存\n3. 分离计算与存储",
            },
        ]
    },
    # 7. 健康评分
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "node_cpu_seconds_total: 45%, node_memory_MemAvailable_bytes: 18GB/32GB, node_filesystem_avail_bytes: 380GB/500GB, node_load1: 1.8",
            },
            {
                "role": "assistant",
                "content": "🟢 系统健康状态良好\n1. CPU 45%，负载适中\n2. 内存可用56.25%，充足\n3. 磁盘可用76%，空间充裕\n4. 负载1.8，平稳\n判断：健康评分92/100\n建议：\n1. 维持现有配置",
            },
        ]
    },
    # 8. CPU正常
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "node_cpu_seconds_total: 35%, 基线40%, node_load1: 1.2, 基线1.5",
            },
            {
                "role": "assistant",
                "content": "🟢 CPU运行正常\n1. CPU使用率35%，低于基线5%\n2. 系统负载1.2，低于基线20%\n判断：CPU资源充足\n建议：\n1. 继续监控趋势",
            },
        ]
    },
    # 9. 容量规划
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "node_memory_MemAvailable_bytes: 8GB/32GB, 7天增长趋势: 每天-800MB, node_filesystem_avail_bytes: 120GB/500GB, 30天趋势: 每天-5GB",
            },
            {
                "role": "assistant",
                "content": "🟡 容量预警\n1. 内存可用25%，按趋势10天后不足\n2. 磁盘可用24%，按趋势24天后不足\n判断：需提前规划扩容\n建议：\n1. 2周内扩容内存\n2. 3周内扩容磁盘\n3. 优化数据清理策略",
            },
        ]
    },
    # 10. 内存泄漏
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "node_memory_MemAvailable_bytes: 4GB/32GB, 24小时前: 12GB, 48小时前: 18GB, 进程内存持续增长",
            },
            {
                "role": "assistant",
                "content": "🔴 疑似内存泄漏\n1. 可用内存从18GB降至4GB，48小时下降77.8%\n2. 呈线性下降趋势，非正常波动\n判断：存在内存泄漏风险\n建议：\n1. 排查内存泄漏进程\n2. 分析应用日志\n3. 必要时重启服务\n4. 部署内存监控",
            },
        ]
    },
]

# 创建输出目录
output_dir = Path("data/dummy")
output_dir.mkdir(parents=True, exist_ok=True)

# 分割数据集
train_samples = samples[:8]
valid_samples = samples[8:]
test_samples = samples[8:]  # 与valid相同


# 写入函数
def write_jsonl(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        for record in data:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(data)


# 写入文件
train_count = write_jsonl(output_dir / "train.jsonl", train_samples)
valid_count = write_jsonl(output_dir / "valid.jsonl", valid_samples)
test_count = write_jsonl(output_dir / "test.jsonl", test_samples)

print(f"✅ 数据生成完成:")
print(f"  - train.jsonl: {train_count} 条样本")
print(f"  - valid.jsonl: {valid_count} 条样本")
print(f"  - test.jsonl: {test_count} 条样本")
