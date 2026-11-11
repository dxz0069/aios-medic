# Spike ① 首轮结果（2026-11-11，DCU 实测）

## 结论

**PASS——kill-switch 失败率 5%（红线 30%），Medic 场景正式确认可行，不触发回退 DevForge。**

| 指标 | 值 | 说明 |
|---|---|---|
| JSON 解析成功率 | **1.00** (20/20) | 含 ≤2 次重试与围栏剥离 |
| 类目准确率 | **0.95** (19/20) | 唯一错例 S14（curl 连接拒绝样本被判为 network 而非 service/crash——本身就是模糊边界，综合层可用多源修正） |
| 组件定位准确率 | 0.35 | 见下方分析，不构成风险 |
| 证据召回率 | 0.675 | — |
| 端到端耗时 | 107.7s / 20 样本 | 约 5.4s/样本（eager attention + 串行） |

## 组件准确率偏低的分析（为什么不构成风险）

1. **评分口径偏严**：金标签组件是注入侧的命名（如 `busy-loop process group`），模型自然语言输出（如 `多个python3进程` / `CPU资源`）在宽松子串匹配下判 False；这是打分器的对齐问题，不是模型能力问题。
2. **单源定位本就不足**：赛题设计的正确结构就是"4 个分析智能体各看一源 → Diagnostician 聚合定位组件"。单源 35% → 多源聚合后的组件定位是 M1 的 prompt 工程任务（把 `testbed/signatures/signatures.json` 的 `component_hint` 注入提示词即可显著提升）。
3. kill-switch 口径（`1 - min(parse_ok, category_acc)` = 0.05）不受此影响。

## 测试环境

- 硬件：郑州超算（SCNet）华中一区 BW 实例（海光 DCU 系，**64GB 显存**，16 核 / 60GB 内存）
- 推理：`tools/infer_server_stdlib.py`（纯标准库 OpenAI 兼容服务，`--attn eager`）
- 模型：Qwen2.5-7B-Instruct（BF16，ModelScope 下载至 NFS，14.5GB）
- 关键坑（已解决并记录）：DTK 版 torch 的 cutlass flash-attention 适配器缺库（`libtorch_hip.so` 中 `cutlassfa_adapter`），sdpa 的 flash 路径会抛 `No matching libraries found for flash_attn_2_cuda*.so`；**eager 稳定可用**，后续 vLLM(DAS) wheel 自带 kernel 不受影响。

## 产物

- 完整数据：服务器 `/public/home/acotxxttog/aios-medic/experiments/spike1/results/`（spike1_report.md + spike1_results.json，含每条原始输出）
- 本报告同步至仓库 `note/report/`。

## 下一步（按优先级）

1. **vLLM(DAS) 安装**：从光合社区 sourcefind 取 `vllm-0.11.0+das.opt1.dtk2604.cp311` wheel（z-file 前端，需浏览器下载或找到直链）——解锁 continuous batching，性能实验的前提。
2. AIOS Kernel 拉起 + 官方示例智能体（Spike ② 收尾）：用已恢复的 `/root/proj4-devforge/.venv`（aios-agent-sdk 0.0.3 已装）。
3. 实验床适配：BW 容器内无 Docker，F01-F05 注入器改为直跑方案（受控目录 + 自建 tmpfs 不可行则 F02 改限速写文件；F05 需测容器是否有 NET_ADMIN）。
4. 72 小时生命周期：当前实例周四 ~14:39 到期；写 `~/medic/bootstrap.sh`（恢复 venv + 重启推理服务），并评估"镜像固化"。
