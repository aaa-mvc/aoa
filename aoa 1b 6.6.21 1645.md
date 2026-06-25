


## GitHub 简介（修订版）

**中文版：**

> OA（面向行动的审计）是人类和人工智能代理执行工作的本地第一审计层。
随着人工智能代理越来越多地执行现实世界的任务，组织面临着一个简单但关键的问题：
实际发生了什么，创造了什么价值？
AOA通过从可观察的活动（如文件修改、Git历史和工作流跟踪）生成可追溯和可解释的证据来回答这个问题。
与人工智能驱动的报告工具不同，AOA不需要大型语言模型、云服务或对文件内容的访问。它完全基于本地元数据和确定性规则进行操作。
关键原则：
本地优先：数据保留在用户的计算机上。
可解释的：每个结论都可以追溯到可观察到的证据。
独立于平台：跨编辑器、存储库和工作流工作。
Human+Agent原生：使用相同的执行模型审核人员和自主代理。
可插入的价值模型：组织定义自己的价值定义。
AOA不是生产力跟踪器。
AOA是一个将操作转化为证据的审计运行时。
在代理时代，执行力是丰富的。信任是稀缺的。
AOA提供证据层。

**English version：**

># AOA

AOA (Action-Oriented Audit) is a local-first audit layer for work performed by both humans and AI agents.

As AI agents increasingly execute real-world tasks, organizations face a simple but critical problem:

**What actually happened, and what value was created?**

AOA answers that question by generating traceable and explainable evidence from observable activity such as file modifications, Git history, and workflow traces.

Unlike AI-powered reporting tools, AOA does not require large language models, cloud services, or access to file contents. It operates entirely on local metadata and deterministic rules.

Key principles:

- Local-first: data remains on the user's machine.
- Explainable: every conclusion can be traced back to observable evidence.
- Platform-independent: works across editors, repositories, and workflows.
- Human + Agent native: audits both people and autonomous agents using the same execution model.
- Pluggable value models: organizations define their own definition of value.

AOA is not a productivity tracker.

AOA is an audit runtime that turns actions into evidence.

In the Agent Era, execution is abundant. Trust is scarce.

AOA provides the evidence layer.
> 
> ## 20 个 GitHub Topics / 搜索关键词

```
1.  audit
2.  behavior-tracking
3.  local-first
4.  privacy-first
5.  offline-first
6.  git-log
7.  filesystem-scanner
8.  time-tracking
9.  productivity
10. work-journal
11. traceability
12. evidence-chain
13. self-hosted
14. zero-ai
15. agent-audit
16. team-analytics
17. cli-tool
18. markdown-report
19. value-evidence
20. state-machine
```
_______________________________________________
==AOA 是一个本地优先（Local-First）的行为审计内核，可以持续追踪人类和 Agent 的工作轨迹，并生成可解释的价值证据链。==

让任何行动者（Human 或 Agent）都留下可验证的价值证据链。

_________________________________
> 真正值钱的是 Trace，不是 Personality。

现在 AOA 手里有的是：

- 文件
    
- Git
    
- 反馈
    
- 节奏
    
- 变化
    
- 趋势
    

这些组合起来就是：

> **Behavior Trace（行为轨迹）**

而在一个「Agent 泡满整个公司」的未来：

> 最大的缺口是：**Agent 在干什么？**

你一句话把 AOA 的真正位置说穿了：

> Trace → Delta → Value → Report  
> = Agent Audit Runtime

这比「周报工具」高了不止一个维度。


AOA = Local-First Behavior Audit Kernel

行为审计内核
_________________________




**AOA 完整演进线：**

```
v0.2        观察自己        delta + semantic + drift
v0.2.1-p    建议自己        🎯 下次建议
v0.2-final  改变自己        policy influence → config 自修改
v0.2.1      不失控          oscillation lock + hard floor
v0.3        记住自己        memory → personality bias
v0.3.1      不变脸          friction = 人格越强越难改
v0.3.2      自稳吸引子      identity + attractor + friction → 三力平衡场
v0.3.3      可解释          causal trace: 每次变化可归因、可反事实 ← 当前
```

**v0.3.3 因果层的能力：**

```json
{
  "to_decision": "stabilizing",
  "dominant_cause": "memory_bias",
  "causes": [
    {"factor": "memory_bias",        "weight": 0.549},
    {"factor": "identity_attractor", "weight": 0.066},
    {"factor": "friction",           "weight": 0.385}
  ],
  "counterfactual": {
    "scenario": "halve memory_bias",
    "would_be_effective": 0.213
  }
}
```

系统现在能回答三个问题：**它做了什么、为什么这样做、如果某个力减半会怎样。**
______________________________________________________
**AOA 完整演进线：**

```
v0.2       观察自己        delta + semantic + drift
v0.2.1-p   建议自己        🎯 下次建议
v0.2-final 改变自己        policy influence → config 自修改
v0.2.1     不失控          oscillation lock + hard floor
v0.3       记住自己        memory → personality bias
v0.3.1     不变脸          friction = 人格越强越难改 ← 当前
```

**v0.3.1 新增的两个物理量：**

|量|作用|极端值时的表现|
|---|---|---|
|**friction**|人格越强 → 越抗拒改变|bias 0.77 → str 0.03（几乎不动）|
|**phase**|系统当前的行为相态|warmup / stable / converging-biased / diverging-biased|

好，这一步我们直接进入“物理级收敛内核”，不再做工程装饰，只保留三件事：







__________________________________________________
##  AOA v0.2 本地测试报告

### 测试矩阵

|#|操作|预期|结果|
|---|---|---|---|
|1|`cli.py run desktop` (首次)|"历史数据不足（1 次）"|✅|
|2|`cli.py run desktop` (第 2 次)|Delta 区段出现|✅ `679→682 (+3)，+0.4%`|
|3|`cli.py run code`|独立 profile，显示"1 次"|✅ 不被 desktop 污染|
|4|`cli.py run brain`|独立 profile，显示"1 次"|✅ 不被 desktop 污染|
|5|`cli.py run desktop` (第 3 次)|Delta 继续，仍无 drift|✅ （历史=2，不够）|
|6|`cli.py run desktop` (第 4 次)|**Drift 激活**|✅ `📈 更收敛`|

### 闭环三层验证

```
第 4 次 desktop 报告中同时出现：

📊 相比上次                          ← Delta 层
  - 文件修改数：686 → 687 (+1)       

变化解读                             ← Semantic 层
  - 文件修改数基本稳定（置信度：高）
  - 注意力正在收敛（置信度：高）

趋势判断                             ← Drift 层
  📈 相比历史基线，当前更收敛
```

### Profile 隔离验证

```
index.json
├── 我的工作简报    → 4 runs   趋势: up（drift ✅）
├── Code Review     → 1 run    无趋势（不受干扰 ✅）
└── Personal Retro  → 1 run    无趋势（不受干扰 ✅）
```

**全部 6 项测试通过。AOA v0.2 闭环成立。**

——————————————————————————————————

## Phase 1b 完成 · AOA v0.2 已推送到 GitHub

### 最终目录结构

```
D:\Brain\AOA\                          ← 新项目根目录
├── cli.py                              ← 统一 CLI 入口
├── README.md                           ← 项目文档
├── .gitignore                          ← 排除 trace_history + reports
├── aoa/                                ← 核心包
│   ├── __init__.py                     ← v0.2.0
│   ├── engine.py                       ← 报告生成
│   ├── trace.py                        ← 结构化 trace 持久化（profile 隔离）
│   ├── delta.py                        ← delta + drift + semantic
│   ├── value.py                        ← 可插拔价值函数
│   └── adapters/
│       ├── __init__.py
│       ├── filesystem.py               ← 文件系统扫描
│       └── git.py                      ← Git log 扫描
├── profiles/                           ← 三个独立 profile
│   ├── desktop/config.json             ← 个人工作全面复盘
│   ├── code/config.json                ← 代码活动聚焦
│   └── brain/config.json               ← 知识库复盘
└── trace_history/                      ← 运行时产物（.gitignore 排除）
    ├── index.json                      ← 按 profile 隔离的运行索引
    └── <run_id>.json                   ← 结构化 trace
```

### 测试结果

|维度|状态|证据|
|---|---|---|
|**CLI 统一入口**|✅|`python cli.py run desktop/code/brain` 全部跑通|
|**Delta**|✅|报告出现"相比上次：+N 文件，±$N"|
|**Semantic**|✅|"文件修改数基本稳定"（置信度：高）+ 证据链|
|**Drift**|✅|"📈 当前更收敛，注意力在集中"（≥3 次后激活）|
|**Profile 隔离**|✅|index.json 按 profile 名称分键存储，互不污染|
|**GitHub**|✅|[https://github.com/aaa-mvc/aoa](https://github.com/aaa-mvc/aoa) 已推送，14 个文件|

### 未变动的旧文件

`D:\Brain\AFA\desktop_review\` 下所有旧文件完整保留：

- `review_engine.py`、`config.json`、`review.bat`、`git_review.py` 均未删除
- `aoa_engine.py`、`aoa_config.json`、`AOA.bat` 也在原地（Phase 1a 产物）
  
  ————————————————————————