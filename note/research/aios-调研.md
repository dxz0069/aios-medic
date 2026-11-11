# AIOS 定点调研笔记

> 调研日期：2026-10-26。调研目的：为"智能体操作系统中的多智能体协作技术"赛题做技术选型，不做铺开式调研，只回答三个问题：AIOS 当前形态如何、"AIOS-Agent SDK"指什么、如何接 7B/8B 端侧模型。
> 以下所有结论均来自公开仓库与文档原文，未做推测；不确定的点在文末"待克隆确认"一节单独列出。

## 1. AIOS 的当前形态：Kernel + SDK 双仓库

AIOS（AI Agent Operating System，Rutgers AGI Research / Yongfeng Zhang 团队）在 2024-11-30 的 v0.2 版本起拆分为两个仓库（来源：AIOS 仓库 README News 一节，https://github.com/agiresearch/AIOS）：

- **AIOS Kernel**（仓库 `agiresearch/AIOS`）：OS 内核抽象层，管理智能体所需的各类资源——LLM、内存（Memory Manager）、存储（Storage Manager）、工具（Tool Manager）、上下文管理（Context Manager）等；智能体的请求经"系统调用链"被调度并分发到各模块执行。
- **AIOS SDK**（仓库 `agiresearch/Cerebrum`，即 Cerebrum，论文全称 *Cerebrum (AIOS SDK): A Platform for Agent Development, Deployment, Distribution, and Discovery*，NAACL 2025）：面向智能体开发者/用户的 SDK，通过调用 AIOS Kernel 提供的能力来构建和运行智能体应用。PyPI 包名 `cerebrum`（2024-11-26 上架）。

赛题原文说"使用 AIOS-Agent SDK 设计多智能体协作系统"，对应的技术路线即：**AIOS Kernel（`agiresearch/AIOS`）+ Cerebrum SDK（`agiresearch/Cerebrum`）**。

注意：`https://github.com/agiresearch/aios-sdk` 当前无法访问（Network error 500），历史 README 中所有 SDK 链接均指向 `agiresearch/Cerebrum`，因此以 Cerebrum 为准；正式开发前需再确认一次该链接状态。

## 2. 关键事实：并发与 2.1x 性能声明的出处

- AIOS 基础论文 *AIOS: LLM Agent Operating System*（arXiv:2403.16971，https://arxiv.org/abs/2403.16971）已被 COLM 2025 接收（2025-07-08 News）。
- 赛题背景中"实测可达最高 2.1 倍性能提升"出自该论文实验部分（2026-11-11 经 ar5iv 全文核实，https://ar5iv.labs.arxiv.org/html/2403.16971 ）：**并发 serving 加速**——最多 250 并发线程、默认 Round Robin 调度、单张 RTX A5000（24GB）、Llama-3.1-8B、HumanEval 基准 + Reflexion 智能体；论文中并无"串行流水线 vs 并发流水线"的端到端对比——那是本赛题定制的更宽松指标。论文评测用的基准是 HumanEval / MINT / GAIA / SWE-Bench-Lite，被测框架为 ReAct / Reflexion / Autogen / Open-Interpreter / MetaGPT。
- AIOS 内含调度器（Scheduler）模块，处理并发智能体请求的调度与上下文切换（README："scheduling, context switch, memory management, storage management, tool management, Agent SDK management"；实验性 Rust 重写 `aios-rs/` 中也列出 scheduler trait）。
- **这是我们"并发比串行快 ≥20%"指标的理论依托：同一套智能体流程，串行逐个执行 vs 交给 AIOS 并发调度，对比端到端墙钟时间。**

## 3. 环境与部署（官方 README 原文要点）

来源：https://github.com/agiresearch/AIOS 与 https://github.com/agiresearch/Cerebrum

- Python 版本：仅支持 **3.10 / 3.11**。
- 安装：克隆两仓库，`pip install -r requirements.txt`（CPU）或 `requirements-cuda.txt`（GPU），Cerebrum 用 `pip install -e .`；装 Kernel 时会自动装上 SDK（Local Kernel 模式下同一台机器装两者即可）。
- 启动 Kernel：`bash runtime/launch_kernel.sh`，或 `python3.x -m uvicorn runtime.launch:app --host 0.0.0.0 --port 8000`（FastAPI/uvicorn 服务）。
- 配置：`aios/config/config.yaml`（推荐直接改文件，避免环境变量同步问题）；CLI 有 `aios env list` / `aios env set` / `aios refresh`。
- 部署模式：Mode 1（本地 Kernel，开发+运行同机）→ Mode 2（远程 Kernel）→ Mode 2.5/3/4（规划中）。**比赛用 Mode 1 即可，最简、故障面最小。**

## 4. 端侧 7B/8B 模型接入（已验证的官方支持）

README "Configure LLM Models" 给出 config.yaml 示例（原文）：

```yaml
llms:
  models:
    # Ollama Models
    - name: "qwen2.5:7b"
      backend: "ollama"
      hostname: "http://localhost:11434"  # Make sure to run ollama server

    # vLLM Models
    - name: "meta-llama/Llama-3.1-8B-Instruct"
      backend: "vllm"
      hostname: "http://localhost:8091/v1"  # Make sure to run vllm server
```

- vLLM 启动：`vllm serve meta-llama/Llama-3.1-8B-Instruct --port 8091`
- ollama 启动：先 `ollama pull qwen2.5:7b`
- 支持的 LLM 后端表：Anthropic / OpenAI / Deepseek / Google / Groq / HuggingFace / **ollama** / **vLLM** / Novita。开源模型的功能调用（function calling）自 2024-06-20 起支持（"Function calling for open-sourced LLMs (native huggingface, vLLM, ollama) is supported"）。
- Deepseek-r1 的 1.5b/7b/8b/... 已支持（2025-01-27 News）。

**选型结论：`vllm serve` 跑 Qwen2.5-7B-Instruct（或 Llama-3.1-8B-Instruct），backend: vllm 接入。** vLLM 的 continuous batching 使并发 LLM 请求真正并行处理，是"并发比串行快"的物理基础；ollama 作为无 GPU 环境的降级方案。

## 5. Cerebrum SDK 的智能体/工具开发方式（README 原文要点）

来源：https://github.com/agiresearch/Cerebrum

- 智能体目录结构（每个智能体一个文件夹）：

```
author_name/
└── agent_name/
      │── entry.py        # 智能体主逻辑
      │── config.json     # 配置与元数据（name/description/tools/meta/build）
      └── meta_requirements.txt  # 额外依赖
```

- config.json 的 `build` 字段指明入口文件与类名（如 `"entry": "agent.py", "module": "DemoAgent"`），`tools` 字段声明依赖工具。
- 运行单个智能体：`run-agent --mode local --agent_path <path> --task "<task_input>"`
- 工具（Tool）开发：`entry.py` 实现 `get_tool_call_format()`（OpenAI function-calling 格式）与 `run(params)` 两个方法；本地工具放 `cerebrum/tool/core/` 并在 `cerebrum/tool/core/registry.py` 注册；代码内加载：`AutoTool.from_preloaded("example/arxiv", local=False)`
- SDK 对外 API 分四类：**LLM APIs / Memory APIs / Storage APIs / Tool APIs**（细页在 docs.aios.foundation，见下）。
- 智能体间互调/消息路由、并发执行多智能体的具体 API 在 README 中未展开——**需要克隆仓库看 `cerebrum/example/` 与源码确认**（见第 7 节）。

## 6. 官方文档与生态入口

- 官方文档站：https://docs.aios.foundation/（GitBook；首页内容与 README 一致，含部署模式说明）
- AIOS Kernel 仓库：https://github.com/agiresearch/AIOS
- Cerebrum（AIOS SDK）仓库：https://github.com/agiresearch/Cerebrum
- 赛题指定论文：
  - AIOS: LLM Agent Operating System — https://arxiv.org/abs/2403.16971
  - Multi-Agent Collaboration Mechanisms: A Survey of LLMs — https://arxiv.org/pdf/2501.06322
- 赛题指定参考仓库（owl，Workforce 式多智能体协作的借鉴来源）：https://github.com/camel-ai/owl
- AgentHub / 应用入口：https://app.aios.foundation
- 支持的智能体框架（可 onboard 到 AIOS）：OpenAGI、AutoGen、Open-Interpreter、MetaGPT
- 相关论文：Cerebrum (AIOS SDK)（NAACL 2025）、A-MEM: Agentic Memory（arXiv:2502.12110）、LiteCUA 计算机使用智能体（arXiv:2505.18829）

## 7. 源码侦察结论（2026-11-11 克隆两仓库 main 分支浅克隆后确认）

克隆位置：`E:\project\competition\aios-ref\`（AIOS 与 Cerebrum，均为仓库外参考目录，不入库）。原"待确认五问"逐一回答：

1. **智能体写法（已确认）**：每个智能体一个目录（`agent.py + config.json`），类需实现 `run(task_input)` 返回 `{"agent_name", "result", "rounds"}`；官方示例 `cerebrum/example/agents/demo_agent/agent.py` 展示了完整模式：`AutoTool.from_batch_preloaded(config["tools"])` 加载工具、manual/automatic 两种工作流、失败重试计数。
2. **LLM 调用 API（已确认，稳定可用）**：`from cerebrum.llm.apis import llm_chat, llm_chat_with_json_output, llm_call_tool, llm_operate_file`——所有 LLM 请求默认路由到 AIOS Kernel（`base_url=aios_kernel_url`，由 `config.get_kernel_url()` 读取），即**走内核调度与上下文管理，这正是赛题要求的"在 AIOS 框架内"**。特别注意 `llm_chat_with_json_output`：SDK 原生 JSON 输出模式，直接服务我们的诊断单结构化需求。
3. **智能体间通信（已确认：不存在）**：全仓库检索 `call_another_agent / send_message / agent_to_agent` 等均无结果。**自建协作中间件（MessageBus + DAGScheduler）从"兜底方案"升级为"必选方案"**——这也是我们在 AIOS 之上的核心贡献点。
4. **客户端分层架构（重构中，勿依赖）**：仓库根 `example/aios_demo.py` 引用了 `cerebrum.client.Cerebrum`（`execute()`/`poll_agent()` 异步执行）与 `OverridesLayer(max_workers)` 调度覆盖层，但当前 main 快照中 `cerebrum/client.py` 与 `overrides/layer.py` **尚不存在**——demo 领先于包代码。M1 应基于稳定的 agent 级 API（第 2 条）开发，持续关注该重构。
5. **智能体分发（已确认）**：`cerebrum/manager/agent.py` 的 `AgentManager` 负责 `package_agent/upload_agent/download_agent`（打包上传到 Kernel 或 AgentHub）；本地运行入口为 `run-agent` CLI（`cerebrum/commands/`）。

对设计的直接影响：M1 的智能体实现直接照 `demo_agent` 模板写 `run(task_input)`；LLM 调用一律走 `llm_chat_with_json_output`（经 Kernel）；MessageBus/DAGScheduler 由我们实现并作为论文/文档中的核心组件。

### 7.1 Spike ② 完成补充（2026-11-11，DCU 容器实测）

全链路已在郑州超算 BW 卡（海光 DCU 64GB）容器内跑通并复现：`run-agent` → 自研 `log_analyst` 智能体 → `llm_chat_with_json_output` → **AIOS Kernel（:8000，vllm 后端）** → 自建 OpenAI 兼容推理服务（:8091，transformers eager，Qwen2.5-7B-Instruct BF16）。S01（dmesg OOM）样本输出：`resource/memory` + `leaky.py`（组件精确命中）+ 完整证据引用，1 轮成功，端到端 5.3s。实测踩坑两条：①Kernel 的 memory provider 必须用 `in-house`（`mem0` 启动时连 Ollama 直接失败）；②官方带工具的示例智能体（如 story_teller）需从 AgentHub 拉工具、外网不通即失败——**Medic 全部智能体按无工具设计**（采集/探测走确定性代码，见 ops/scnet/README.md 坑 8-10）。

## 8. 对本赛题的直接启示

1. "AIOS-Agent SDK" = Cerebrum，智能体按 `entry.py + config.json` 规范开发，我们的 6 类智能体即 6 个符合该规范的智能体包，天然满足"在 AIOS 框架内"。
2. vLLM + 7B 的接入是官方一等公民，性能实验基础牢靠。
3. 2.1x 声明来自 AIOS 论文的调度实验，我们的 20% 指标只是它的保守下限，设计上应瞄准更高并给出分解分析。
4. 智能体通信与编排可能是 SDK 薄弱点，方案设计里自建轻量协作层（消息总线 + DAG 调度器）作为兜底，这在"操作系统"语境下反而是加分项（相当于给 AIOS 写了一个多智能体中间件）。
