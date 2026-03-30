# 快速开始指南

## 环境要求

- Node.js 18+ 
- npm 或 yarn 或 pnpm

## 安装步骤

### 1. 安装依赖

```bash
cd rag_frontend
npm install
```

### 2. 配置环境变量

创建 `.env` 文件或编辑现有文件：

```env
VITE_API_BASE=http://127.0.0.1:8000
VITE_APP_TITLE=RAG知识库系统
```

### 3. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:5173

### 4. 构建生产版本

```bash
npm run build
npm run preview  # 预览生产构建
```

## 主要功能入口

### 登录/注册
- `/login` - 用户登录
- `/register` - 用户注册

### 核心功能（需要登录）
- `/` - 智能对话（RAG）
- `/search` - 知识搜索
- `/documents` - 文档管理
- `/knowledge` - 知识库管理
- `/sessions` - 会话历史
- `/knowledge-graph` - 知识图谱

### 管理员功能（需要管理员权限）
- `/enterprise` - 企业管理
- `/logs` - 日志查看
- `/audit/upload` - 审计上传
- `/audit/result/:id` - 审计结果

### 个人设置
- `/profile` - 个人资料

## 典型工作流程

### 1. 创建知识库并上传文档

1. 访问 `/knowledge` 页面
2. 点击 "创建知识库" 按钮
3. 输入知识库名称和描述
4. 创建成功后，访问 `/documents`
5. 选择知识库，上传文档文件

### 2. 进行智能对话

1. 访问首页 `/`
2. 在左侧选择要使用的知识库
3. 在输入框中输入问题
4. 系统会自动从知识库中检索相关内容并生成回答

### 3. 语义搜索

1. 访问 `/search` 页面
2. 选择要搜索的知识库
3. 输入搜索关键词
4. 查看搜索结果

### 4. 企业管理员操作

1. 以管理员身份登录
2. 访问 `/enterprise`
3. 查看企业信息和管理用户
4. 生成邀请码邀请新用户

## 认证流程

系统使用 JWT Token 进行认证：

1. 用户登录后，Token 存储在 localStorage
2. 所有 API 请求自动携带 Token
3. Token 过期后需要重新登录

## API 文档

完整的后端 API 文档请参考项目根目录的 `api-docs.md` 文件。

## 技术栈

- **前端框架**: Vue 3 + TypeScript
- **状态管理**: Pinia
- **路由**: Vue Router
- **样式**: Tailwind CSS
- **构建工具**: Vite
- **图标**: Lucide Vue Next

## 项目结构

```
rag_frontend/
├── src/
│   ├── api/          # API 接口
│   ├── components/    # 可复用组件
│   ├── composables/   # 组合式函数
│   ├── locales/      # 国际化文件
│   ├── router/       # 路由配置
│   ├── stores/       # Pinia 状态管理
│   ├── types/        # TypeScript 类型
│   ├── utils/        # 工具函数
│   └── views/        # 页面组件
├── public/           # 静态资源
└── dist/            # 构建产物
```

## 常见问题

### Q: 登录后无法访问需要认证的页面？
A: 检查 Token 是否正确存储，确保 API 服务正常运行。

### Q: 上传文档失败？
A: 检查文件格式是否支持（PDF、TXT、DOC、DOCX、PNG），确保文件大小在限制范围内。

### Q: 聊天没有返回结果？
A: 确保知识库中已有上传的文档，并且文档已处理完成。

### Q: 如何切换语言？
A: 在布局组件中找到语言切换按钮。

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证。
