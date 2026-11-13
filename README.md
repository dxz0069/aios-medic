# Medic — 基于多智能体协作的 Linux 故障诊断与自愈系统

> 运行于 AIOS（AI Agent Operating System）之上的多智能体协作系统：在受控 Linux 环境中注入系统故障，由 9 类智能体协作完成 **检测 → 并行诊断 → 根因定位 → 受控修复 → 验证 → 报告** 的全流程自动化。

**参赛信息**：2026 年全国大学生计算机系统能力大赛·操作系统设计赛·中西部与华南区域赛·功能挑战赛道 A 类赛题《智能体操作系统中的多智能体协作技术》。

**技术栈**：Linux (Ubuntu 22.04 / 兼容 openKylin) · [AIOS Kernel](https://github.com/agiresearch/AIOS) · [Cerebrum (AIOS SDK)](https://github.com/agiresearch/Cerebrum) · Qwen2.5-7B-Instruct（vLLM 端侧部署）

## 系统架构

```
┌─────────────────── 受控实验床（容器沙箱） ────────────────────┐
│  FaultInjector 故障注入器    HealthProbes 健康探针           │
└──────────────▲──────────────────────────▲───────────────────┘
               │ 采集                      │ 水位/状态
┌──────────────┴──────────────────────────┴───────────────────┐
│              AIOS Kernel（LLM/内存/存储/工具/调度）           │
├──────────────────────────────────────────────────────────────┤
│  协作中间件：MessageBus · DAGScheduler · SharedWorkspace     │
├──────────────────────────────────────────────────────────────┤
│  智能体层（9 类）                                             │
│  Commander · Log/Metric/Proc/Net Analyst（4 路并行）          │
│  Diagnostician · Repairer · Verifier · Reporter              │
└──────────────────────────────────────────────────────────────┘
```

多智能体协作满足赛题全部硬性要求：≥4 种智能体（9 类）、≥4 个可并行子任务（4 路并行分析 + 报告链）、≥3 对双向交互（5 对，含质询回采/修复-验证回环）、DAG 依赖与顺序约束（告警→计划→并行分析→综合→修复→验证→交付）。

## 仓库结构

```
agents/         9 类智能体（遵循 Cerebrum SDK 智能体包规范，M0 定版后填充）
middleware/     协作中间件：MessageBus / DAGScheduler / SharedWorkspace
testbed/        受控实验床：故障目录、注入器、健康探针、特征签名库
experiments/    实验脚本与数据（Spike 验证、正确性协议、性能对比协议）
docs/           正式设计实现文档（提交版）
note/           过程笔记：调研、选题决策、设计方案、比赛计划
```

## 快速开始

```bash
# 1) 模型服务（WSL2/Linux，16GB+ 显存用 AWQ 量化；24GB 可跑 BF16）
vllm serve Qwen/Qwen2.5-7B-Instruct-AWQ --port 8091

# 2) Spike ①：7B 诊断单输出可靠性测试（20 条样本）
python experiments/spike1/run_spike1.py --base-url http://127.0.0.1:8091/v1 \
       --model Qwen/Qwen2.5-7B-Instruct-AWQ

# 3) 实验床：构建沙箱镜像并注入故障
docker build -t medic-sandbox -f testbed/sandbox/Dockerfile testbed/
bash testbed/run_sandbox.sh          # 启动一次性沙箱
python3 testbed/injector/inject.py F01 --action inject   # 注入内存泄漏
python3 testbed/probes/probes.py                        # 健康探针
python3 testbed/injector/inject.py F01 --action clear    # 清除
```

## 当前状态

- [x] 调研与选题决策（2026-11-11 锁定 Medic，见 `note/research/`）
- [x] M0 三个 Spike 全部 PASS（7B 诊断单可靠性 kill-switch 失败率 5%）
- [x] M1 全系统：9 类智能体 + 协作中间件 + 全闭环流水线（诊断→修复→验证→报告）
- [x] M2 实验床：**8 类可注入故障**（F01-F06/F10/F18）+ 健康探针 + 确定性签名库 + 单元测试 10 项全绿（CI 覆盖）
- [x] M3 性能与正确性实验：多轮套件 + 18 轮稳定性浸泡 + 单智能体对照（数据见 `experiments/m1_demo/report/`，v2f 最佳配置整体提速 24.1%，恢复率 17/18）
- [ ] M4 文档最终化与提交材料（进行中）

**实验结论速览**（详见 `docs/设计实现文档.md`）：五类故障中四类并发提速显著（F01 27.9%、F04 18.6-37.4%、F02 47.3%、F05 25.1%）；F03（CPU 饱和）在"故障存续期间在线诊断"时因算力争用出现负优化——已定位为系统在极端资源剥夺下的真实行为并以快照模式对照验证。

## 文档与测试

- [设计实现文档](docs/设计实现文档.md)（提交版主体）
- [AIOS 调研笔记](note/research/aios-调研.md) · [赛题深度分析与选题决策](note/research/赛题深度分析与选题决策.md) · [系统设计方案](note/design/系统设计方案.md) · [比赛总体计划](note/plan/比赛总体计划.md) · [Spike① 报告](note/report/spike1-首轮.md)
- 实验数据归档：`experiments/m1_demo/report/`（v2-v2g 六代套件 + soak + 对照）
- 单元测试：`python -m pytest tests/ -q`（10 项，纯本地）；CI：GitHub Actions（Python 3.10/3.11）

## 参考与致谢

- [AIOS: LLM Agent Operating System (COLM 2025)](https://arxiv.org/abs/2403.16971) / [AIOS Kernel](https://github.com/agiresearch/AIOS) / [Cerebrum SDK](https://github.com/agiresearch/Cerebrum)
- [Multi-Agent Collaboration Mechanisms: A Survey of LLMs](https://arxiv.org/pdf/2501.06322)
