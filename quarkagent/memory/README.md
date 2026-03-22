# QuarkAgent Memory

`quarkagent/memory/` 提供 QuarkAgent 的上下文记忆模块，用来缓解长对话、多轮任务和工具调用带来的上下文膨胀问题。

它的核心目标不是单纯“保存更多历史”，而是把历史拆成不同价值层级，并在每一轮只把当前真正有用的部分注入到 Prompt 中。

## 设计目标

- 控制上下文长度，避免历史消息无限增长
- 保持短期对话连续性，不破坏当前多轮交流
- 把高价值信息结构化沉淀，而不是长期依赖原始对话
- 支持按主题、按 query 的相关历史召回
- 保持持久化兼容性，允许旧 memory 文件继续加载

## 记忆分层设计

当前实现采用“短期工作记忆 + 长期压缩记忆 + 结构化状态记忆 + 按需召回”的分层策略。

| 记忆层级 | 实现方式 | 主要作用 | 当前实现特点 |
|---|---|---|---|
| 短期工作记忆 | 保留最近若干轮原始消息 | 维持当前对话连续性，支持即时上下文理解 | 使用 `messages` 保存，默认窗口大小为 `12` |
| 长期认知摘要 | 对溢出的旧消息进行滚动压缩 | 避免历史原文无限膨胀 | 使用 `rolling_summary` 保存压缩摘要 |
| 主题片段记忆 | 把被压缩的旧消息组织成 episode | 按主题保留历史片段，便于后续召回 | 使用 `episodes` 保存 topic、summary、keywords |
| 任务状态记忆 | 将目标、计划、待办、阻塞单独结构化存储 | 保留“当前正在做什么”而不是依赖聊天文本恢复 | 使用 `task_state` 保存 `goal / topic / todo / done / blockers` |
| 决策记忆 | 单独记录关键决策与理由 | 防止长流程中反复推翻已确认方案 | 使用 `decision_log` 保存 `decision / rationale` |
| 用户稳定记忆 | 保存偏好与事实 | 避免重复询问用户长期稳定信息 | 使用 `preferences` 和 `facts` 保存 |
| 查询感知召回 | 按 query 计算词项重叠选择 episode 和 decision | 只把相关历史带回 Prompt，减少噪声 | 在 `context(query = ...)` 中动态选择 top-k 相关片段 |

## 处理流程

### 1. 写入阶段

每次调用 `Memory.push(role, content)` 时：

- 新消息先进入 `messages`
- 如果是用户消息，会更新 `task_state["topic"]` 和 `task_state["latest_user_request"]`
- 当 `messages` 超过阈值时，旧消息会被压缩

### 2. 压缩阶段

当短期消息超过 `max_messages` 后：

- 保留最近 `preserve_recent_messages` 条消息
- 把更早的消息压缩成一个 episode
- episode 摘要追加到 `rolling_summary`

这样做的结果是：

- 当前窗口仍然保留新鲜原文
- 老历史不会丢失，而是转成低成本长期记忆

### 3. 召回阶段

调用 `Memory.context(query = ...)` 时，会按顺序组织上下文：

- `preferences`
- `facts`
- `task_state`
- 相关 `decision_log`
- 相关 `episodes`
- `rolling_summary`
- 最近对话

同时会做字符预算裁剪，确保最终上下文长度可控。

## 为什么这样设计

如果只保留“最近 N 条消息 + 一份全局摘要”，会有两个问题：

1. 摘要会越来越肥
2. 不相关的历史也会被一并带回当前 Prompt

当前设计通过把信息拆成不同层级来解决：

- 需要即时推理的，放在短期消息
- 需要长期保留脉络的，压缩进摘要和 episodes
- 需要稳定恢复任务进度的，放在 task state
- 需要长期坚持的架构选择，放在 decision log
- 需要时再召回的，通过 query-aware retrieval 选出

## 当前代码结构

```text
quarkagent/memory/
├── __init__.py
├── constants.py
├── core.py
├── schemas.py
├── storage.py
└── README.md
```

### 文件职责

- `__init__.py`
  - 暴露稳定导出接口：`Memory`、`MemorySummary`、`list_memory_summaries`
- `constants.py`
  - 存放默认阈值、停用词、logger 等常量
- `schemas.py`
  - 定义 `MemorySummary`
- `storage.py`
  - 负责 memory 文件路径管理、文件列表和摘要索引
- `core.py`
  - 负责 `Memory` 主逻辑，包括压缩、结构化状态、召回和上下文渲染

## 对外使用方式

### 基本导入

```python
from quarkagent.memory import Memory, list_memory_summaries
```

### 记录对话

```python
memory = Memory(agent_scope = "main")
memory.push("user", "帮我设计一个记忆模块")
memory.push("assistant", "可以从分层记忆开始")
```

### 记录结构化任务状态

```python
memory.set_task_state(
    goal = "实现上下文记忆模块",
    todo = ["拆分模块", "补测试", "写 README"],
    blockers = ["需要控制 Prompt 长度"]
)
```

### 记录关键决策

```python
memory.record_decision(
    decision = "使用启发式压缩而不是额外 LLM 摘要",
    rationale = "降低依赖和运行成本"
)
```

### 构造查询感知上下文

```python
context_text = memory.context(query = "如何做相关历史召回")
```

## 与 Agent 的集成方式

这个模块已经集成到 QuarkAgent 的运行时流程中：

- CLI 启动时创建 `Memory` 实例
- `QuarkAgent` 每轮构造 runtime prompt 时动态调用 memory provider
- subagent 也使用同样的 memory 机制
- resolved runtime prompt 仍然会持久化，便于调试和回放

因此现在的记忆系统不是“启动时拼一次静态文本”，而是“每轮按当前 query 动态组装上下文”。

## 持久化格式

当前 memory 文件会保存以下主要字段：

- `preferences`
- `facts`
- `messages`
- `rolling_summary`
- `task_state`
- `episodes`
- `decision_log`
- `system_prompt`
- `tools`
- `skills`
- `task_id`

旧版 memory 文件即使没有新字段，也可以继续加载。

## 适用场景

- 多轮产品设计讨论
- 代码代理的长任务执行
- 带工具调用的复杂问答
- 需要长期记住用户偏好、任务状态和关键决策的智能体

## 后续可扩展方向

当前版本是一个轻量、可落地的 MVP，后续可以继续扩展：

- 引入 embedding 检索，替代当前词项重叠评分
- 将压缩策略拆成独立 `compression.py`
- 将检索策略拆成独立 `retrieval.py`
- 增加显式的记忆更新策略，如冲突检测和记忆失效
- 为不同 agent scope 设计不同的 memory policy

## 总结

这个模块的核心思想可以概括为：

> 不是把所有历史都带进上下文，而是把历史压缩、结构化，并在需要时只召回最相关的部分。

这也是 QuarkAgent 当前 memory 设计用来应对超长上下文问题的主要方法。
