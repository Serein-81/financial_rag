# 项目整理说明

## 整理日期
2026-04-12

## 整理概述

本次整理对项目进行了系统化的重组，主要包括：
- 测试文件的统一管理
- 文档文件的分类整理
- 代码结构的优化

---

## 1. 测试文件整理

### 整理位置
所有测试文件已统一移至 `rag_backend/tests/` 目录

### 目录结构
```
rag_backend/tests/
├── api_tests/              # API测试
├── integration_tests/       # 集成测试
├── test_data/             # 测试数据（SQL文件、Excel测试数据）
├── scripts/               # 测试脚本（PowerShell、Bash）
└── [测试脚本文件]          # Python测试文件
```

### 整理的文件类型
- **Python测试文件**：`test_*.py`, `check_*.py`
- **测试脚本**：`test_*.ps1`, `test_*.sh`
- **SQL测试数据**：`*.sql`
- **Excel测试数据**：`*.xlsx`
- **诊断和调试脚本**：`diagnose_*.py`, `debug_*.py`

### 不提交规则
根据 `.gitignore` 配置，以下文件不会被提交：
- `rag_backend/tests/` 目录
- `rag_frontend/tests/` 目录
- 临时测试文件

---

## 2. 文档整理

### 整理位置
所有文档已统一移至项目根目录的 `docs/` 目录

### 目录结构
```
docs/
├── implementation/    # 实现文档和规划
├── troubleshooting/   # 故障排除和修复指南
├── guides/          # 使用指南
└── testing/         # 测试相关文档
```

### 文档分类说明

#### implementation/ (实现文档)
- 项目结构和总结文档
- 功能实现报告
- 系统改进计划
- 架构设计文档

#### troubleshooting/ (故障排除)
- 问题诊断指南
- 修复总结文档
- 性能优化指南
- 上传问题解决方案

#### guides/ (使用指南)
- 快速开始指南
- 前端测试指南
- 动画效果配置指南
- 优化配置文档

#### testing/ (测试文档)
- 测试结果文档
- 请求到达测试
- 性能测试报告

---

## 3. 提交历史

### 最近提交
```
b42001e feat: Complete project restructuring and organization
```

### 提交内容
- ✅ 重组测试文件到rag_backend/tests/
- ✅ 分类整理文档到docs/目录
- ✅ 添加新的前端组件和API端点
- ✅ 实现新功能（Agent中心、财务管理、税务系统等）
- ✅ 更新Docker配置
- ✅ 整理调试和诊断脚本

---

## 4. Git状态

- **当前分支**：`main`
- **本地提交**：1个提交领先于 origin/main
- **工作树状态**：干净（无未提交更改）

### 推送远程
如需将更改推送到远程仓库，执行：
```bash
git push origin main
```

---

## 5. 注意事项

### 测试文件管理
- 所有新的测试文件应放在 `rag_backend/tests/` 目录
- 测试数据放在 `test_data/` 子目录
- 测试脚本放在 `scripts/` 子目录

### 文档维护
- 实现类文档放在 `docs/implementation/`
- 故障排除文档放在 `docs/troubleshooting/`
- 使用指南放在 `docs/guides/`

### .gitignore配置
确保以下内容在 `.gitignore` 中：
```
rag_backend/tests/
rag_frontend/tests/
```

---

## 6. 项目结构概览

```
My_rag/
├── docs/                      # 整理后的文档目录
│   ├── implementation/       # 实现文档
│   ├── troubleshooting/       # 故障排除文档
│   ├── guides/               # 使用指南
│   └── testing/              # 测试文档
├── rag_backend/              # 后端服务
│   ├── tests/               # 整理后的测试目录
│   │   ├── api_tests/
│   │   ├── integration_tests/
│   │   ├── test_data/
│   │   ├── scripts/
│   │   └── [测试文件]
│   ├── app/                  # 应用代码
│   ├── alembic/             # 数据库迁移
│   └── ...
├── rag_frontend/             # 前端服务
│   ├── src/                  # 源代码
│   ├── tests/               # 前端测试
│   └── ...
├── mcp_server/               # MCP服务
└── ...
```

---

## 7. 后续建议

### 定期整理
- 每完成一个功能模块后，及时将测试文件移入tests目录
- 维护性文档定期更新到docs对应目录
- 清理临时调试脚本

### 代码审查
- 确保新功能有对应的测试文件
- 测试文件命名规范：`test_<功能>_<场景>.py`
- 保持文档与代码同步更新

### 版本控制
- 提交信息应清晰描述更改内容
- 大型重构单独提交，便于回溯
- 定期推送代码到远程仓库

---

## 8. 联系方式

如有整理相关问题，请查阅：
- 项目README: `README.md`
- 故障排除: `docs/troubleshooting/`
- 实现文档: `docs/implementation/`
