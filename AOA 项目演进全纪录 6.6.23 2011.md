AOA 项目演进全纪录
起点
D:\Brain\AFA\desktop_review\config.json — 8 行 JSON，一个扫描文件时间戳生成个人工作简报的脚本。

阶段一：从脚本到操作系统内核（v0.2 系列）
版本	做了什么	获得的能力
v0.2	delta + semantic + drift	观察自己——看到变化、解释变化、判断趋势
v0.2.1-p	🎯 下次建议	建议自己——系统基于 drift 给出操作建议
v0.2-final	Policy Influence	改变自己——drift 信号修改下次运行的 config
v0.2.1	Stability Kernel	不失控——oscillation lock + hard floor + runaway brake
阶段二：人格系统（v0.3 系列）
版本	做了什么	获得的能力
v0.3	Memory Kernel	记住自己——累积行为历史形成人格偏置
v0.3.1	Friction 阻尼	不变脸——人格越强越抗拒改变
v0.3.2	Identity + Attractor	自稳吸引子——三力平衡场，向"自己是谁"收敛
v0.3.3	Causal Memory	可解释——每次变化可归因、可反事实
阶段三：从个人工具到团队产品（v0.4–v0.5）
版本	做了什么	获得的能力
v0.4	Feedback Window	吐槽窗口——员工在报告底部写三行，管理者一键汇总
v0.5	user.json + visibility	角色裁剪——同一份数据，self/manager/hr/boss 看到不同内容
v0.5.1	Interactive Mode	双击即用——数字选单，零命令记忆
v0.5.2	终端直接输出	一键到底——报告打印到终端，不弹窗、不闪退
阶段四：Agent 审计（v0.6–v0.8）
版本	做了什么	获得的能力
v0.6	Agent Trace Adapter	审计 Claude Code——解析 JSONL transcript，生成 Agent 报告
v0.6.1	Agent Discovery	发现本机所有 Agent——python cli.py discover agents
v0.6.2-3	会话标题 + 子Agent名 + 关键词	知道 Agent 在聊什么
v0.7	Capability Trace	能力分布——工具调用归类为代码生成/项目分析/命令执行/搜索研究
v0.7.1	Project Mapping	项目分布——从文件路径自动归属项目，Agent 的时间花在哪
v0.7.2	Artifact Evidence	可观测产出——新建文件数、修改文件数、Git 提交数不再是"估算"
v0.8	Asset Registry	加权资产——不同类型产出有不同价值权重（code×1.0, commit×2.0, test×3.0）
v0.8.1	Artifact Extractor	文件→资产自动分类——按扩展名归类，自动提取项目名
v0.8.2	Artifact Ledger	统一资产账本——可查询、可导出、按类别/按项目分组
v0.8.3	Project Graph	Agent 投资组合——每个项目的操作数 + 资产数 + 资产分
v0.8.4	Real Value Engine	证据驱动价值——每个价值点可追溯到具体文件，不再用"$1900/ROI "拍脑袋
v0.8.5	Artifact Graph	一屏决策——python cli.py graph claude-agent 给 CTO 30 秒看完
最终产出的完整证据链

python cli.py graph claude-agent
一屏输出：


  Actions ........... 2,732
  Artifacts ......... 827

  [Capabilities]
    命令执行  ||||||||||||||||||  848
    代码生成  |||||||||||||||||   818
    项目分析  ||||||||||||||||    756
    任务规划  ||||||              233

  [Projects]
    AOA   |||||||||||||||  157 actions  score 380
    ASA   ||||||||||||     120 actions  score 210
    AGA   |||||||||         84 actions  score 195
    AFA   ||||||||          77 actions  score 140

  Value Score ....... 963
  Cost .............. $63
  Value/Cost ........ 15:1
五个问题一行答案： Agent 干了什么？生产了什么？用在了哪些项目上？创造了多少价值？值不值这个成本？

技术资产
层	文件	职责
入口	cli.py	统一 CLI + 交互菜单 + graph/discover/aggregate 命令
报告	aoa/engine.py	Markdown 报告生成 + visibility 裁剪
追踪	aoa/trace.py	结构化 trace 持久化 + profile 隔离
差异	aoa/delta.py	delta/drift/semantic 三合一
价值	aoa/value.py	可插拔价值函数
记忆	aoa/memory.py	bias/identity/attractor/friction（已冻结为内部引擎）
因果	aoa/causal.py	因果归因链 + 反事实
资产	aoa/artifact.py + aoa/artifact_extractor.py + aoa/ledger.py	类型注册 + 文件分类 + 统一账本
适配器	aoa/adapters/filesystem.py git.py agent_trace.py	Human 审计 + Git 审计 + Agent 审计
一句话总结
从一份 8 行 JSON 出发，在几个小时、26 次提交内，长成了一个能回答"任何 Human 或 Agent 做了什么、创造了什么、值多少、证据在哪"的完整行为审计内核。