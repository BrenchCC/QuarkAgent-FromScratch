# Utils 模块

为 QuarkAgent 框架提供的工具函数和类集合。

## 概述

`utils` 模块提供了 QuarkAgent 系统中广泛使用的核心辅助功能，包括：

- JSON 序列化/反序列化工具
- 大型语言模型（LLM）相关工具
- 反射和自我批评功能
- 其他通用工具函数

## 模块说明

### 1. `json_util.py`

提供全面的 JSON 序列化和反序列化工具，支持：

- 自定义类型处理
- 错误处理和验证
- 用于调试的美化打印
- 复杂数据结构的处理

### 2. `llm_util.py`

LLM 相关的工具函数包括：

- 模型配置管理
- 提示模板处理
- 响应解析和提取
- API 交互辅助函数

### 3. `reflector.py`

用于通过自我反思和批评增强代理响应的 Reflector 类：

- 分析对话历史
- 基于多个标准评估响应质量
- 通过 LLM 反思生成改进的响应
- 处理反射过程的错误恢复

## 使用示例

### Reflector 使用

```python
from miniagent.utils.reflector import Reflector

# 使用 LLM 客户端初始化反射器
reflector = Reflector(client=llm_client, model="gpt-4")

# 对对话应用反射
improved_messages = reflector.apply_reflection(messages)
```

### JSON 工具使用

```python
from miniagent.utils.json_util import safe_json_dump, safe_json_load

# 安全的 JSON 序列化
with open("data.json", "w") as f:
    safe_json_dump(data, f, indent=2)

# 安全的 JSON 反序列化
with open("data.json", "r") as f:
    data = safe_json_load(f)
```

## 安装

utils 模块作为 MiniAgent 框架的一部分提供，无需额外安装。

## 要求

- Python 3.8+
- 项目 `requirements.txt` 中指定的依赖项

## 许可证

此模块是 MiniAgent 项目的一部分，并以相同的许可证发布。