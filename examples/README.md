# QuarkAgent Examples

这是 QuarkAgent 项目的示例和测试集合，展示了如何使用和测试 QuarkAgent 的各项功能。

## 🌟 项目概述

QuarkAgent 是一个轻量级的 CLI AI 编程助手，具有以下核心特性：
- 智能编程助手，像 Claude Code 一样写代码、修复 Bug、运行测试
- 轻量级实现，核心逻辑简洁高效
- 多模型支持，兼容 OpenAI、Claude、DeepSeek 等所有兼容 OpenAI 接口的模型
- 高度可扩展，极简的装饰器模式，轻松挂载自定义工具
- 内置丰富工具，提供代码操作、文件管理、系统命令等常用工具
- 支持会话记忆功能，保持上下文连贯性
- 简洁易用的命令行界面

## 📁 示例文件说明

### 1. 运行所有测试
**文件**: `run_all_tests.py`

这是一个测试套件运行器，用于执行所有 QuarkAgent 测试脚本。它会自动检测并运行 examples 目录下的所有测试文件。

**使用方法**:
```bash
python run_all_tests.py
```

### 2. 基础功能测试
**文件**: `test_agent_basic.py`

测试 QuarkAgent 的基础功能，包括：
- 代理初始化
- 工具管理功能
- 工具描述构建
- JSON 提取方法
- 工具调用解析

**使用方法**:
```bash
python test_agent_basic.py
```

### 3. CLI 功能测试
**文件**: `test_cli.py`

测试 QuarkAgent 的命令行界面功能，包括：
- CLI 参数解析
- 配置加载
- 会话管理
- 命令执行

**使用方法**:
```bash
python test_cli.py
```

### 4. 配置管理测试
**文件**: `test_config.py`

测试配置管理系统，包括：
- 配置文件加载
- 环境变量读取
- 配置验证
- 默认配置设置

**使用方法**:
```bash
python test_config.py
```

### 5. JSON 工具测试
**文件**: `test_json_llm_utils.py`

测试 JSON 处理工具，包括：
- JSON 解析和验证
- 工具调用格式化
- 响应处理

**使用方法**:
```bash
python test_json_llm_utils.py
```

### 6. 记忆功能测试
**文件**: `test_memory.py`

测试会话记忆功能，包括：
- 对话历史记录
- 上下文恢复
- 记忆存储和加载

**使用方法**:
```bash
python test_memory.py
```

### 7. 反思器测试
**文件**: `test_reflector.py`

测试反思器功能，包括：
- 响应评估
- 错误分析
- 改进建议

**使用方法**:
```bash
python test_reflector.py
```

### 8. 工具功能测试
**文件**: `test_tools.py`

测试内置工具的功能，包括：
- 代码操作工具（read、write、edit、grep、glob）
- 系统控制工具（open_browser、open_app、create_docx、clipboard_copy）
- 实用工具（calculator）

**使用方法**:
```bash
python test_tools.py
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd /path/to/QuarkAgent-FromScratch
pip install -r requirements.txt
pip install -e .  # 安装 quarkagent 命令
```

### 2. 配置

创建 `.env` 文件：
```bash
LLM_API_KEY=your_api_key_here
LLM_MODEL=gpt-4o
LLM_API_BASE=https://api.openai.com/v1
```

### 3. 运行示例

**运行所有测试**:
```bash
cd examples
python run_all_tests.py
```

**运行单个测试文件**:
```bash
cd examples
python test_agent_basic.py
```

## 🔍 项目结构

```
examples/
├── __init__.py          # 包初始化文件
├── run_all_tests.py     # 测试套件运行器
├── test_agent_basic.py  # 基础功能测试
├── test_cli.py          # CLI 功能测试
├── test_config.py       # 配置管理测试
├── test_json_llm_utils.py  # JSON 工具测试
├── test_memory.py       # 记忆功能测试
├── test_reflector.py    # 反思器测试
└── test_tools.py        # 工具功能测试
```

## 💡 使用提示

1. **测试顺序**: 建议按照以下顺序运行测试：
   1. `test_json_llm_utils.py` (基础工具)
   2. `test_agent_basic.py` (核心功能)
   3. `test_tools.py` (工具功能)
   4. `test_memory.py` (记忆功能)
   5. `test_config.py` (配置管理)
   6. `test_cli.py` (CLI 界面)
   7. `test_reflector.py` (反思器)

2. **调试模式**: 可以在运行测试时添加 `-v` 或 `--verbose` 参数查看详细输出

3. **环境变量**: 确保在运行测试前已经正确配置了 `.env` 文件

## 🐛 常见问题

1. **API 密钥错误**: 确保 `.env` 文件中的 `LLM_API_KEY` 是有效的
2. **网络连接问题**: 某些测试需要网络连接，请确保您的网络正常
3. **依赖问题**: 如果遇到模块找不到的错误，请重新安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 📚 更多资源

- [项目主 README](../README.md) - 项目概述和完整文档
- [QuarkAgent 文档](https://github.com/BrenchCC/QuarkAgent-FromScratch/wiki) - 详细使用指南
- [API 文档](https://brenchcc.github.io/QuarkAgent-FromScratch) - 自动生成的 API 文档

## 🤝 贡献

如果您有任何建议或想要添加新的示例，请查看 [CONTRIBUTING.md](../CONTRIBUTING.md) 文件了解如何贡献。

## 📄 许可证

这些示例代码遵循与项目相同的 [MIT 许可证](../LICENSE)。
