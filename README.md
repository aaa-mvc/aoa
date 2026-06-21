# AOA — Action-Oriented Audit

**一个本地优先（Local-First）的行为审计内核，用文件时间戳和 Git 轨迹，为 Human & Agent 生成可解释的价值证据链。**

> 不生成、不杜撰、不预测。不依赖 AI。不依赖网络。所有输出可追溯至磁盘上的真实数据。

---

## 一句话

AOA 回答一个问题：**"这段时间，到底做了什么？值多少？"**

---

## 三个场景

| 场景 | 谁用 | 回答什么问题 |
|------|------|------------|
| **个人** | 开发者 / 知识工作者 | 我的时间去哪了？ |
| **团队** | Tech Lead / 管理者 | 团队到底在干什么？瓶颈在哪？ |
| **Agent** | Agent 使用者 / 运维 | 这个 Agent 到底创造了什么价值？ |

---

## 30 秒开始

```bash
# 零依赖（仅需 Python 3.10+）
git clone https://github.com/aaa-mvc/aoa.git
cd aoa

# 交互模式（推荐）：双击即用，数字选单
python cli.py interactive

# 命令行模式
python cli.py run desktop                    # 个人：全面复盘
python cli.py run desktop --audience manager # 主管视角
python cli.py aggregate feedback             # 管理者：汇总全部反馈
```

---

## 输入 → 内核 → 输出

```
Inputs（真实数据）          Kernel（状态执行内核）          Outputs（可验证产出）
─────────────────         ─────────────────────         ─────────────────
文件修改时间戳 (mtime)      State  →  Delta              📄 结构化报告
Git commit log              ↓                            📊 行为趋势 & 偏离检测
员工反馈 (--feedback)      Drift  →  Policy             💰 价值估算（模型可替换）
员工身份 (user.json)        ↓                            🔍 因果归因链
角色权限 (visibility)      Trace  →  Memory             📋 反馈汇总（aggregate）
                           ↓
                      → 一切可审计、可回放
```

---

## 核心特性

- **零 AI 依赖** — 纯统计规则，不调 LLM，不编造内容
- **零网络依赖** — 所有数据来自本地磁盘，不出机器
- **零侵入** — 只读文件修改时间戳（mtime），不录屏、不记键鼠、不看文件内容
- **可插拔价值模型** — 每个组织/角色定义自己的"什么是价值"
- **角色裁剪** — `--audience self|manager|hr|boss` 同一份数据不同视角
- **反馈聚合** — 员工在报告底部写三行，管理者一条命令看到全部
- **持续自校准** — 内核有内部偏置/阻尼机制，越用越了解用户行为模式，建议越精准

---

## 架构

```
cli.py                          ← 统一入口（命令行 + 交互菜单）
aoa/
├── engine.py                   ← 报告生成引擎
├── trace.py                    ← 结构化 trace 持久化（审计链）
├── delta.py                    ← 状态差 + 偏离检测 + 语义解释
├── value.py                    ← 可插拔价值函数
├── memory.py                   ← 行为记忆 & 内部偏置（引擎机制，非对外卖点）
├── causal.py                   ← 因果归因：每一次策略调整可追溯
└── adapters/
    ├── filesystem.py           ← 文件系统扫描适配器
    └── git.py                  ← Git log 扫描适配器
profiles/
├── desktop/                    ← 个人工作复盘
│   ├── config.json             ←   扫描什么 + 谁看什么
│   └── user.json               ←   我是谁
├── code/                       ← 代码活动聚焦
└── brain/                      ← 知识库复盘
```

---

## 与竞品的区别

| | AOA | ScreenPipe | 飞书/钉钉 | git-standup |
|---|---|---|---|---|
| 数据来源 | 文件 mtime + git | 截屏 + OCR | 生态内文档/日历 | 仅 git |
| AI 依赖 | **零** | 强依赖 LLM | 强依赖 LLM | 可选 |
| 网络依赖 | **零** | 本地 | 云端 | 本地 |
| 隐私侵入 | **最低**（只看时间戳） | 高（录屏） | 中 | 低 |
| 价值模型 | **可替换** | 固定 | 固定 | 无 |
| 角色裁剪 | **内置** | 无 | 有 | 无 |
| 人格/自适应 | **有**（内核内部） | 无 | 无 | 无 |

---

## 版本

当前版本：**v0.5** — 已具备完整的 State → Delta → Drift → Policy → Trace → Memory → Causal 闭环。

内核演进历程：[CHANGELOG](https://github.com/aaa-mvc/aoa/commits/main)

---

## 灵感

受 LabVLA（具身 Agent 的 State → Action → State 闭环）启发，将"行为审计"抽象为一个与领域无关的状态执行内核。

---

## 许可

MIT
