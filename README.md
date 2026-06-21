# AOA — Action-Oriented Audit

**用真实数据追踪"你做了什么、是否偏离了基线、产生了多少价值"的状态执行内核。**

> 灵感来自 LabVLA 的 State → Action → State 闭环思想。  
> AOA 不生成、不杜撰、不预测——所有输出来自可验证的本地数据源。

---

## 快速开始

```bash
# 安装依赖（仅需 Python 3.10+，无第三方依赖）
pip install -e .

# 运行
python cli.py run desktop    # 个人工作简报
python cli.py run code       # 代码活动复盘
python cli.py run brain      # 知识库复盘
```

第一次运行后，报告底部的"趋势判断"会提示数据不足。连续运行 3 次后自动激活 drift 检测。

---

## Profile 说明

| Profile | 数据源 | 扫描目录 | 用途 |
|---------|--------|----------|------|
| `desktop` | 文件 mtime | D:/Brain + D:/LabVLA | 个人工作全面复盘 |
| `code` | 文件 mtime | D:/LabVLA + D:/Brain/AFA | 代码活动聚焦 |
| `brain` | 文件 mtime | D:/Brain | 知识库活动 |

---

## 输出

每次运行产出两份文件：

1. **Markdown 报告** — 包含每日节奏、类型分布、价值估算、delta（相比上次）、drift（趋势判断）
2. **结构化 Trace JSON** — 保存在 `trace_history/` 目录，可审计、可回放

---

## 架构

```
cli.py                          ← 统一入口
aoa/
├── engine.py                   ← 报告生成
├── trace.py                    ← 结构化 trace 持久化
├── delta.py                    ← delta + drift + semantic
├── value.py                    ← 可插拔价值函数
└── adapters/
    ├── filesystem.py           ← 文件系统扫描
    └── git.py                  ← Git log 扫描
profiles/
├── desktop/config.json
├── code/config.json
└── brain/config.json
```

---

## 许可

MIT
