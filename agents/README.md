# agents/ — 智能体层（9 类角色）

> 状态：占位骨架。M0 Spike ②（Cerebrum SDK 能力摸底）完成后，按其确认的智能体包规范（`entry.py + config.json + meta_requirements.txt`）填充实现。

| 角色 | 类型 | 职责 | 输入 → 输出 |
|---|---|---|---|
| Commander | 编排 | 生成诊断计划 DAG、分发任务、异常重规划 | 告警 → 计划 JSON |
| LogAnalyst | 分析（并行） | journalctl/dmesg 片段异常抽取 | 日志片段 → 诊断单 JSON |
| MetricAnalyst | 分析（并行） | sar/proc 时序水位异常判定 | 指标片段 → 诊断单 JSON |
| ProcAnalyst | 分析（并行） | 进程/资源快照异常定位 | 进程快照 → 诊断单 JSON |
| NetAnalyst | 分析（并行） | 网络状态（ss/ping/tc）异常判定 | 网络状态 → 诊断单 JSON |
| Diagnostician | 综合 | 多源证据聚合，根因结论 + 修复方案 | 诊断单集合 → 根因 JSON |
| Repairer | 执行 | 白名单修复动作执行 | 修复方案 → 动作日志 |
| Verifier | 验证 | 健康探针判定，失败回环 Repairer | 探针结果 → 验证结论 |
| Reporter | 报告 | 人话诊断报告并行起草 | 全部工件 → report.md |

统一约定（详见 `note/design/系统设计方案.md` §3/§6）：

1. 分析类智能体共享同一基类，按「源特化提示词 + 专用采集工具 + 输出 Schema」实例化为 4 种类型；
2. 智能体间一切交互走 MessageBus，消息带 `from/to/type/round/ts/payload`，全量落盘；
3. 诊断单输出为结构化 JSON（异常事件/证据/置信度/建议补采项），解析失败重试 ≤2 次后由确定性签名库兜底；
4. 确定性工作（采集命令、探针、文件读写）不交给 LLM。
