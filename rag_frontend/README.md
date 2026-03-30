# RAG 知识库系统 - 前端

一个现代化、美观的 RAG（检索增强生成）知识库管理系统前端应用。

## 功能特性

- 🎨 **现代化 UI** - 采用亮色主题，渐变色设计，流畅的动画效果
- 💬 **智能对话** - 支持流式对话，实时显示 AI 回复
- 📚 **知识库管理** - 创建、选择、管理多个知识库
- 📄 **文档上传** - 支持拖拽上传，自动向量化处理
- 🔍 **语义搜索** - 基于向量的智能搜索功能
- 🔐 **用户认证** - 安全的登录注册系统
- 📱 **响应式设计** - 适配各种屏幕尺寸

## 技术栈

- **Vue 3** - 渐进式 JavaScript 框架
- **TypeScript** - 类型安全
- **Vite** - 快速的构建工具
- **Pinia** - 状态管理
- **Vue Router** - 路由管理
- **Tailwind CSS** - 实用优先的 CSS 框架
- **Lucide Icons** - 美观的图标库
- **Marked** - Markdown 渲染
- **DOMPurify** - XSS 防护

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 配置环境变量

创建 `.env` 文件（已创建，默认配置）：

```env
VITE_API_BASE=http://127.0.0.1:8000
```

### 3. 启动开发服务器

```bash
npm run dev
```

应用将在 `http://localhost:5173` 启动

### 4. 构建生产版本

```bash
npm run build
```

## 项目结构

```
rag_frontend/
├── src/
│   ├── api/              # API 调用
│   │   ├── chat.ts       # 聊天接口
│   │   ├── knowledge.ts  # 知识库接口
│   │   └── session.ts    # 会话接口
│   ├── components/       # 可复用组件
│   ├── config/           # 配置文件
│   │   └── api.ts        # API 配置
│   ├── router/           # 路由配置
│   │   └── index.ts
│   ├── stores/           # Pinia 状态管理
│   │   ├── auth.ts       # 认证状态
│   │   ├── knowledge.ts  # 知识库状态
│   │   └── session.ts    # 会话状态
│   ├── types/            # TypeScript 类型定义
│   │   └── index.ts
│   ├── utils/            # 工具函数
│   │   ├── request.ts    # HTTP 请求封装
│   │   ├── markdown.ts   # Markdown 处理
│   │   └── time.ts       # 时间格式化
│   ├── views/            # 页面组件
│   │   ├── ModernLoginView.vue      # 登录页
│   │   ├── ModernRegisterView.vue   # 注册页
│   │   ├── ModernChatView.vue       # 聊天页
│   │   ├── ModernUploadView.vue     # 上传页
│   │   ├── ModernDocumentsView.vue  # 文档管理页
│   │   └── ModernSearchView.vue     # 搜索页
│   ├── App.vue           # 根组件
│   ├── main.ts           # 入口文件
│   └── style.css         # 全局样式
├── .env                  # 环境变量
├── package.json          # 项目配置
├── tailwind.config.js    # Tailwind 配置
├── tsconfig.json         # TypeScript 配置
└── vite.config.ts        # Vite 配置
```

## 主要页面

### 登录页面 (`/login`)
- 美观的渐变背景
- 表单验证
- 错误提示

### 注册页面 (`/register`)
- 完整的注册表单
- 密码确认
- 实时验证

### 聊天页面 (`/`)
- 侧边栏显示历史会话
- 流式对话显示
- Markdown 渲染
- 来源引用显示
- 知识库选择
- 创建新会话

### 上传页面 (`/upload`)
- 拖拽上传
- 文件类型验证
- 上传进度显示
- 处理状态反馈

### 文档管理页面 (`/documents`)
- 文档列表展示
- 状态标识（处理中、已完成、失败）
- 文档详情
- 删除功能

### 搜索页面 (`/search`)
- 语义搜索
- 结果高亮
- 相似度评分
- 来源文件显示

## API 接口

所有接口都已根据后端 API 文档正确配置：

- **认证**: `/api/v1/auth/*`
- **知识库**: `/api/v1/knowledge/*`
- **聊天**: `/api/v1/chat/*`
- **会话**: `/api/v1/sessions/*`
- **搜索**: `/api/v1/search/*`

## 开发说明

### 添加新页面

1. 在 `src/views/` 创建新的 Vue 组件
2. 在 `src/router/index.ts` 添加路由配置
3. 如需认证，设置 `meta: { requiresAuth: true }`

### 添加新的 API

1. 在 `src/api/` 创建新的 API 文件
2. 使用 `request` 或 `requestForm` 工具函数
3. 在 `src/types/index.ts` 定义类型

### 状态管理

使用 Pinia 进行状态管理：

```typescript
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
authStore.login(email, password)
```

## 样式指南

- 使用 Tailwind CSS 实用类
- 渐变色：`from-blue-500 to-purple-600`
- 圆角：`rounded-xl` 或 `rounded-2xl`
- 阴影：`shadow-md` 或 `shadow-lg`
- 过渡：`transition-all duration-200`

## 浏览器支持

- Chrome (推荐)
- Firefox
- Safari
- Edge

## 常见问题

### 1. 无法连接后端？

检查 `.env` 文件中的 `VITE_API_BASE` 是否正确。

### 2. 登录失败？

确保后端服务正在运行，并且使用正确的邮箱和密码。

### 3. 文件上传失败？

检查文件类型是否支持（PDF, DOC, DOCX, TXT, PNG）。

## 许可证

MIT License

## 作者

RAG Terminal Team

---

**享受使用！** 🚀
