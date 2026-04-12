# 🔧 前端加载超时 - 故障排除指南

## 快速检查清单

### ✅ 1. 清除浏览器缓存
```
按 Ctrl + Shift + R (强制刷新)
或
按 Ctrl + F5
或
使用无痕/隐私模式打开
```

### ✅ 2. 检查后端服务
```bash
# 确保后端服务正在运行
cd D:\Python\Codebase\My_rag\rag_backend
python -m uvicorn app.main:app --reload --port 8000
```

访问以下地址确认后端正常：
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/

### ✅ 3. 检查前端服务
```bash
# 在新终端中启动前端
cd D:\Python\Codebase\My_rag\rag_frontend
npm run dev
```

## 常见问题及解决方案

### 问题 1: 浏览器一直显示加载中

**原因**: 某个组件在初始化时阻塞了

**排查步骤**:
1. 打开浏览器开发者工具 (F12)
2. 切换到 Network 标签
3. 查看是否有请求一直处于 pending 状态
4. 切换到 Console 标签，查看错误信息

**解决方案**:
```typescript
// 如果看到 "EventSource" 错误，说明 SSE 连接失败
// 检查后端服务是否启动
```

### 问题 2: SSE 连接失败

**错误信息**:
```
Failed to construct 'EventSource': 
The URL must be same origin with the page
```

**解决方案**:
1. 确保前端和后端运行在不同端口（已在 vite 配置中处理）
2. 检查 vite 代理配置

### 问题 3: 模块导入错误

**错误信息**:
```
Module not found: Error: Can't resolve '@/components/xxx'
```

**解决方案**:
```bash
# 重启前端服务
npm run dev
```

### 问题 4: TypeScript 类型错误

**错误信息**:
```
TS2307: Cannot find module '@/types/tax-workflow'
```

**解决方案**:
```bash
# 检查文件是否存在
ls D:\Python\Codebase\My_rag\rag_frontend\src\types\tax-workflow.ts
ls D:\Python\Codebase\My_rag\rag_frontend\src\hooks\useTaxWorkflow.ts

# 如果不存在，重新创建
```

### 问题 5: 依赖项缺失

**错误信息**:
```
Cannot find module 'element-plus'
```

**解决方案**:
```bash
cd D:\Python\Codebase\My_rag\rag_frontend
npm install
```

## 诊断命令

### 检查后端
```bash
# Python 语法检查
cd D:\Python\Codebase\My_rag\rag_backend
python -m py_compile app/main.py
python -m py_compile app/api/v1/endpoints/workflow_events.py

# 启动后端（查看错误信息）
python -m uvicorn app.main:app --reload --port 8000
```

### 检查前端
```bash
# TypeScript 类型检查
cd D:\Python\Codebase\My_rag\rag_frontend
npx vue-tsc --noEmit

# 构建检查
npm run build

# 开发模式
npm run dev
```

### 检查文件完整性
```powershell
# 列出我们创建的文件
Get-ChildItem -Path D:\Python\Codebase\My_rag\rag_frontend\src -Recurse -Filter "*Workflow*" | Select-Object FullName

Get-ChildItem -Path D:\Python\Codebase\My_rag\rag_frontend\src -Recurse -Filter "*Review*" | Select-Object FullName

Get-ChildItem -Path D:\Python\Codebase\My_rag\rag_backend\app\langgraph -Recurse -Filter "*.py" | Select-Object FullName
```

## 快速修复

### 如果你不使用工作流功能

暂时注释掉可能导致问题的导入：

**文件**: `D:\Python\Codebase\My_rag\rag_frontend\src\components\TaxSubmissionWorkflow.vue`

**临时解决方案**:
```typescript
// 在文件顶部添加注释，临时禁用
// 注意：这只是临时解决方案！
// import { useTaxWorkflow } from '@/hooks/useTaxWorkflow'
```

### 如果你想保留工作流功能但暂时不用

1. **确保后端正在运行**
2. **清除浏览器缓存**
3. **使用无痕模式打开浏览器**

## 联系支持

如果以上方法都不能解决问题：

1. 打开浏览器开发者工具 (F12)
2. 切换到 Console 标签
3. 复制所有错误信息
4. 切换到 Network 标签
5. 查看哪些请求失败
6. 将这些信息保存并联系开发团队

## 回滚方案

如果需要暂时移除工作流功能：

### 1. 备份文件
```powershell
Copy-Item -Path "D:\Python\Codebase\My_rag\rag_frontend\src\hooks\useTaxWorkflow.ts" -Destination "D:\Python\Codebase\My_rag\backup\"
Copy-Item -Path "D:\Python\Codebase\My_rag\rag_frontend\src\types\tax-workflow.ts" -Destination "D:\Python\Codebase\My_rag\backup\"
Copy-Item -Path "D:\Python\Codebase\My_rag\rag_frontend\src\components\*Workflow*.vue" -Destination "D:\Python\Codebase\My_rag\backup\"
```

### 2. 删除工作流文件
```powershell
Remove-Item -Path "D:\Python\Codebase\My_rag\rag_frontend\src\hooks\useTaxWorkflow.ts"
Remove-Item -Path "D:\Python\Codebase\My_rag\rag_frontend\src\types\tax-workflow.ts"
Remove-Item -Path "D:\Python\Codebase\My_rag\rag_frontend\src\components\*Workflow*.vue"
Remove-Item -Path "D:\Python\Codebase\My_rag\rag_frontend\src\components\HumanReviewDialog.vue"
```

### 3. 清理后端
```powershell
# 可选：移除后端工作流模块（如果不需要）
# 注意：这可能会影响其他功能
```

## 诊断信息收集

请提供以下信息以便更好地帮助您：

1. **错误信息**: 浏览器控制台中的错误
2. **网络请求**: 失败的请求截图
3. **操作步骤**: 出现问题的操作顺序
4. **环境信息**:
   - 操作系统版本
   - 浏览器版本
   - Node.js 版本 (node -v)
   - Python 版本 (python --version)

---

**最后更新**: 2026-04-10  
**适用版本**: 1.0.0
