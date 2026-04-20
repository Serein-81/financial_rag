# RAG 企业智能系统 - 前端

企业级 RAG（检索增强生成）智能助手系统前端应用，集成多智能体协作、财务管理、政策分析、税务工作流等企业级功能。

## 🎯 核心功能

### 🤖 智能对话
- **单智能体对话** - 基于知识库的智能问答
- **多智能体协作** - 财务、法律、税务等领域专家协同
- **群组聊天** - 多用户实时协作讨论
- **意图分类调试** - 智能路由可视化调试

### 💼 企业管理
- **企业用户管理** - 多租户架构，角色权限管理
- **知识库管理** - 多知识库创建、文档管理、向量检索
- **知识图谱** - 可视化知识关系编辑与管理
- **财务数据** - 收入、支出、利润等数据录入与分析
- **财务健康度** - 企业财务状况评估与分析

### 📑 文档处理
- **智能上传** - 支持 PDF、DOC、DOCX、TXT、PNG 等格式
- **合同审查** - AI 辅助合同风险识别与分析
- **安全审计** - 系统日志与安全事件监控
- **文档管理** - 文档列表、状态追踪、详情查看

### 🏛️ 政策服务
- **政策检索** - 基于向量的智能政策匹配
- **政策跟踪** - 企业相关政策订阅与提醒
- **政策详情** - 详细政策内容查看与解析
- **政策匹配** - 企业与政策智能匹配推荐

### 📊 税务工作流
- **税务申报** - 全流程税务申报工作流
- **税务分析** - 税务智能分析与建议
- **数据导入** - Excel/CSV 数据批量导入
- **工作流监控** - 申报进度实时监控

### 🔧 系统工具
- **Agent 中心** - 多智能体监控与管理
- **意图分类** - 智能路由算法调试
- **HITL 审批** - 人机协作审批工作流
- **任务管理** - 企业任务分配与跟踪

### 📈 数据分析
- **分析仪表板** - 多维度数据可视化展示
- **聊天日志** - 对话历史查询与分析
- **运营日志** - 系统运营状态监控
- **通知中心** - 统一消息通知管理

## 🛠️ 技术栈

### 前端框架
- **Vue 3.4+** - 渐进式 JavaScript 框架
- **TypeScript 5.3+** - 类型安全
- **Vite 5.0+** - 快速构建工具
- **Pinia** - 状态管理
- **Vue Router 4** - 路由管理

### UI 框架与样式
- **Tailwind CSS 3.4** - 实用优先 CSS 框架
- **Element Plus 2.9** - Vue 3 组件库
- **Lucide Icons** - 图标库
- **heroicons** - Heroicons 图标

### 动画与可视化
- **GSAP 3.15** - 专业动画引擎
- **vue-motion / @vueuse/motion** - Vue 动画库
- **ECharts 6.0 / vue-echarts** - 数据可视化图表
- **D3.js 7.9** - 数据驱动文档
- **TSParticles** - 粒子效果
- **vue-content-placeholders** - 骨架屏
- **vue-virtual-scroller** - 虚拟滚动

### AI 与数据处理
- **marked** - Markdown 渲染
- **highlight.js** - 代码高亮
- **DOMPurify** - XSS 安全防护
- **mammoth** - Word 文档解析
- **docx** - Word 文档生成

### 工具库
- **@vueuse/core** - Vue 组合式工具集
- **@vueuse/gesture** - 手势识别
- **vue-i18n** - 国际化
- **dayjs / date-fns** - 日期处理
- **axios** - HTTP 请求
- **vuedraggable** - 拖拽排序

## 📁 项目结构

```
rag_frontend/
├── src/
│   ├── api/                      # API 接口层
│   │   ├── auth.ts              # 认证接口
│   │   ├── chat.ts              # 聊天接口
│   │   ├── knowledge.ts         # 知识库接口
│   │   ├── session.ts           # 会话接口
│   │   ├── search.ts            # 搜索接口
│   │   ├── multi-agent.ts       # 多智能体接口
│   │   ├── financial-*.ts      # 财务相关接口
│   │   ├── policy-*.ts          # 政策相关接口
│   │   ├── tax-*.ts             # 税务相关接口
│   │   ├── contract-*.ts        # 合同相关接口
│   │   ├── audit.ts             # 审计接口
│   │   ├── enterprise.ts        # 企业管理接口
│   │   ├── agent-*.ts           # 智能体相关接口
│   │   ├── observability.ts     # 可观测性接口
│   │   ├── security.ts          # 安全监控接口
│   │   └── index.ts             # API 统一导出
│   │
│   ├── components/              # 通用组件
│   │   ├── MainLayout.vue       # 主布局组件
│   │   ├── LoadingIndicator.vue # 加载指示器
│   │   ├── NotificationBar.vue # 通知栏
│   │   ├── HumanReviewDialog.vue # 人工审核对话框
│   │   ├── TaxWorkflow*.vue     # 税务工作流组件
│   │   └── *.vue                # 其他业务组件
│   │
│   ├── composables/             # 组合式函数
│   │   ├── useAnimations.ts     # 动画工具
│   │   ├── useTheme.ts          # 主题管理
│   │   ├── useToast.ts          # 通知提示
│   │   ├── useExport.ts         # 导出功能
│   │   ├── useEnterpriseTheme.ts # 企业主题
│   │   ├── useUnifiedNotifications.ts # 统一通知
│   │   └── *.ts                 # 其他工具函数
│   │
│   ├── config/                  # 配置文件
│   │   └── api.ts               # API 配置
│   │
│   ├── hooks/                   # 自定义 Hooks
│   │   └── useTaxWorkflow.ts    # 税务工作流 Hook
│   │
│   ├── locales/                 # 国际化资源
│   │   ├── zh-CN.ts             # 中文
│   │   ├── en-US.ts             # 英文
│   │   └── index.ts             # 导出配置
│   │
│   ├── router/                 # 路由配置
│   │   └── index.ts             # 路由定义与守卫
│   │
│   ├── stores/                  # Pinia 状态管理
│   │   ├── auth.ts              # 认证状态
│   │   ├── session.ts           # 会话状态
│   │   ├── knowledge.ts         # 知识库状态
│   │   └── group-chat.ts        # 群组聊天状态
│   │
│   ├── types/                   # TypeScript 类型定义
│   │   ├── index.ts             # 通用类型
│   │   ├── review.ts           # 审核类型
│   │   ├── tax.ts              # 税务类型
│   │   └── tax-workflow.ts     # 税务工作流类型
│   │
│   ├── utils/                   # 工具函数
│   │   ├── request.ts          # HTTP 请求封装
│   │   ├── markdown.ts         # Markdown 渲染
│   │   ├── stream.ts           # 流式响应处理
│   │   └── time.ts             # 时间格式化
│   │
│   ├── views/                   # 页面组件
│   │   ├── auth/               # 认证页面
│   │   │   ├── ModernLoginView.vue
│   │   │   └── ModernRegisterView.vue
│   │   │
│   │   ├── chat/               # 对话页面
│   │   │   ├── ModernChatView.vue
│   │   │   ├── MultiAgentChatView.vue
│   │   │   └── GroupChatView.vue
│   │   │
│   │   ├── knowledge/          # 知识库页面
│   │   │   ├── KnowledgeManagementView.vue
│   │   │   ├── ModernKnowledgeDetailView.vue
│   │   │   ├── KnowledgeGraphView.vue
│   │   │   └── KnowledgeGraphEditorView.vue
│   │   │
│   │   ├── document/           # 文档管理页面
│   │   │   ├── ModernDocumentsView.vue
│   │   │   ├── ModernUploadView.vue
│   │   │   └── ChatLogsView.vue
│   │   │
│   │   ├── search/            # 搜索页面
│   │   │   ├── ModernSearchView.vue
│   │   │   └── IntentClassifierDebugView.vue
│   │   │
│   │   ├── financial/         # 财务页面
│   │   │   ├── FinancialDataListView.vue
│   │   │   ├── FinancialDataEntryView.vue
│   │   │   └── FinancialHealthView.vue
│   │   │
│   │   ├── policy/            # 政策页面
│   │   │   ├── PolicyListView.vue
│   │   │   ├── PolicyDetailView.vue
│   │   │   ├── PolicySearchView.vue
│   │   │   └── PolicyNotificationView.vue
│   │   │
│   │   ├── tax/              # 税务页面
│   │   │   ├── TaxSubmissionView.vue
│   │   │   ├── TaxUploadDebug.vue
│   │   │   ├── TaxUploadDiagnostic.vue
│   │   │   ├── TaxIntelligenceView.vue
│   │   │   └── TaxReportUploadView.vue
│   │   │
│   │   ├── audit/            # 审计页面
│   │   │   ├── AuditUploadView.vue
│   │   │   ├── AuditResultView.vue
│   │   │   └── SecurityAuditView.vue
│   │   │
│   │   ├── contract/         # 合同页面
│   │   │   └── ContractReviewView.vue
│   │   │
│   │   ├── enterprise/       # 企业页面
│   │   │   ├── EnterpriseView.vue
│   │   │   └── EnterpriseMatchView.vue
│   │   │
│   │   ├── agent/           # Agent 页面
│   │   │   ├── AgentCenterView.vue
│   │   │   ├── AgentTraceView.vue
│   │   │   ├── MultiAgentMonitorView.vue
│   │   │   └── AnimationDemoView.vue
│   │   │
│   │   ├── workflow/        # 工作流页面
│   │   │   ├── WorkflowDashboardView.vue
│   │   │   ├── WorkflowDetailView.vue
│   │   │   ├── TaxWorkflowMonitorView.vue
│   │   │   ├── PolicyWorkflowMonitorView.vue
│   │   │   └── HITLApprovalView.vue
│   │   │
│   │   ├── analytics/      # 分析页面
│   │   │   ├── AnalyticsDashboard.vue
│   │   │   └── ReviewDashboard.vue
│   │   │
│   │   └── system/        # 系统页面
│   │       ├── SystemOverviewView.vue
│   │       ├── LogsView.vue
│   │       ├── TaskManagementView.vue
│   │       ├── NotificationCenterView.vue
│   │       ├── ReviewCenterView.vue
│   │       └── ModernProfileView.vue
│   │
│   ├── App.vue              # 根组件
│   ├── main.ts              # 应用入口
│   └── style.css            # 全局样式
│
├── tests/                   # 测试文件
│   └── multi-agent-features.test.ts
│
├── .env.example             # 环境变量示例
├── package.json             # 项目配置
├── vite.config.ts          # Vite 配置
├── tailwind.config.js      # Tailwind 配置
├── tsconfig.json           # TypeScript 配置
└── README.md               # 项目文档
```

## 🚀 快速开始

### 环境要求
- Node.js >= 18.0.0
- npm >= 9.0.0

### 1. 安装依赖

```bash
npm install
```

### 2. 环境配置

创建 `.env` 文件：

```env
VITE_API_BASE=http://127.0.0.1:8000
VITE_APP_TITLE=RAG 企业智能系统
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

### 5. 预览生产构建

```bash
npm run preview
```

## 📋 主要页面路由

### 认证模块
| 路由 | 页面 | 说明 |
|------|------|------|
| `/login` | 登录页 | 用户登录 |
| `/register` | 注册页 | 用户注册 |

### 核心功能
| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 智能对话 | 单智能体对话 |
| `/multi-agent` | 多智能体协作 | 多 Agent 协同 |
| `/group-chat` | 群组聊天 | 多人实时讨论 |
| `/search` | 语义搜索 | 智能检索 |

### 知识管理
| 路由 | 页面 | 说明 |
|------|------|------|
| `/knowledge` | 知识库管理 | 知识库列表 |
| `/knowledge/:id` | 知识库详情 | 单个知识库管理 |
| `/knowledge-graph` | 知识图谱 | 可视化知识关系 |
| `/documents` | 文档管理 | 文档列表与状态 |

### 财务模块
| 路由 | 页面 | 说明 |
|------|------|------|
| `/financial-data-list` | 财务数据 | 收入支出列表 |
| `/financial-data-entry` | 数据录入 | 新增财务数据 |
| `/financial-health` | 财务健康度 | 企业财务评估 |

### 政策服务
| 路由 | 页面 | 说明 |
|------|------|------|
| `/policy` | 政策列表 | 政策检索浏览 |
| `/policy/:id` | 政策详情 | 政策内容查看 |
| `/policy-search` | 政策搜索 | 智能政策匹配 |
| `/policy-notifications` | 政策提醒 | 订阅通知管理 |

### 税务工作流
| 路由 | 页面 | 说明 |
|------|------|------|
| `/tax-submission` | 税务申报 | 申报工作流 |
| `/tax-intelligence` | 税务分析 | 智能税务建议 |
| `/tax-upload-debug` | 数据导入 | 调试工具 |

### 文档处理
| 路由 | 页面 | 说明 |
|------|------|------|
| `/contract-review` | 合同审查 | 合同风险分析 |
| `/audit/upload` | 文档审计 | 上传审计文件 |
| `/audit/result/:id` | 审计结果 | 查看审计报告 |

### 企业管理 (需管理员权限)
| 路由 | 页面 | 说明 |
|------|------|------|
| `/enterprise` | 企业管理 | 用户与企业管理 |
| `/enterprise-match` | 企业匹配 | 政策企业匹配 |

### 系统工具 (需管理员权限)
| 路由 | 页面 | 说明 |
|------|------|------|
| `/agent-center` | Agent 中心 | 智能体监控管理 |
| `/intent-debug` | 意图分类 | 路由调试工具 |
| `/security-audit` | 安全审计 | 安全事件监控 |
| `/hitl-approval` | HITL 审批 | 人工审核队列 |

### 工作流与监控
| 路由 | 页面 | 说明 |
|------|------|------|
| `/analytics` | 分析仪表板 | 数据可视化 |
| `/workflow-dashboard` | 工作流总览 | 工作流监控 |
| `/task-management` | 任务管理 | 任务分配跟踪 |

### 个人中心
| 路由 | 页面 | 说明 |
|------|------|------|
| `/profile` | 个人资料 | 用户信息管理 |
| `/notifications` | 通知中心 | 消息通知 |
| `/logs` | 运营日志 | 系统日志查看 |

## 🔌 API 接口

所有接口基于后端 RESTful API，统一前缀 `/api/v1`：

| 模块 | 前缀 | 说明 |
|------|------|------|
| 认证 | `/api/v1/auth/*` | 登录、注册、用户信息 |
| 知识库 | `/api/v1/knowledge/*` | 知识库 CRUD |
| 文档 | `/api/v1/documents/*` | 文档管理 |
| 会话 | `/api/v1/sessions/*` | 对话会话管理 |
| 聊天 | `/api/v1/chat/*` | 对话与消息 |
| 搜索 | `/api/v1/search/*` | 向量检索 |
| 多智能体 | `/api/v1/multi-agent/*` | Agent 协作 |
| 财务 | `/api/v1/financial/*` | 财务数据管理 |
| 政策 | `/api/v1/policy/*` | 政策服务 |
| 税务 | `/api/v1/tax/*` | 税务工作流 |
| 合同 | `/api/v1/contract/*` | 合同审查 |
| 审计 | `/api/v1/audit/*` | 文档审计 |
| 企业 | `/api/v1/enterprise/*` | 企业管理 |
| 通知 | `/api/v1/notifications/*` | 消息通知 |
| 监控 | `/api/v1/observability/*` | 系统监控 |

## 🛡️ 权限控制

系统采用基于角色的访问控制 (RBAC)：

| 角色 | 权限说明 |
|------|----------|
| **普通用户** | 对话、搜索、知识库、文档、个人中心 |
| **管理员** | 全部功能，包含系统配置、用户管理 |

路由守卫会自动检查认证状态和权限：

```typescript
// 需要登录
meta: { requiresAuth: true }

// 需要管理员权限
meta: { requiresAuth: true, requiresAdmin: true }
```

## 🎨 动画与交互

系统集成了丰富的动画效果，支持平滑降级：

### 动画偏好设置
- 自动检测 `prefers-reduced-motion` 无障碍设置
- 自动识别低性能设备并降级
- 聊天消息气泡入场动画
- 打字机效果（AI 回复）
- 骨架屏加载动画
- 数字滚动动画（统计面板）

### 自定义 Hook
```typescript
import { useAnimationPreference } from '@/composables/useAnimations'

const { shouldAnimate } = useAnimationPreference()
```

## 🌐 国际化

系统支持多语言切换：

```typescript
// 中文
import { zhCN } from '@/locales'

// 英文
import { enUS } from '@/locales'
```

当前支持：
- 简体中文 (zh-CN)
- 英文 (en-US)

## 📦 部署说明

### Docker 部署

```bash
# 构建镜像
docker build -t rag-frontend:latest .

# 运行容器
docker run -d -p 5173:80 --name rag-frontend rag-frontend:latest
```

### Nginx 配置

项目包含预配置 `nginx.conf`，支持：
- SPA 路由 fallback
- 静态资源缓存
- Gzip 压缩
- **HTTPS/SSL Termination（已配置）**
  - HTTP → HTTPS 自动重定向
  - 自签名证书（本地测试用）
  - 安全响应头（HSTS, X-Frame-Options 等）
  - TLS 1.2/1.3 协议支持

> ℹ️ **提示**: 详细的 HTTPS 部署指南请查看 [HTTPS_DEPLOYMENT.md](./HTTPS_DEPLOYMENT.md)

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `VITE_API_BASE` | 后端 API 地址 | `http://127.0.0.1:8000` |
| `VITE_APP_TITLE` | 应用标题 | `RAG 企业智能系统` |

## 🔧 开发指南

### 添加新页面

1. 在 `src/views/` 创建 Vue 组件
2. 在 `src/router/index.ts` 添加路由
3. 如需认证：`meta: { requiresAuth: true }`
4. 如需管理员：`meta: { requiresAdmin: true }`

```typescript
{
  path: '/new-page',
  name: 'new-page',
  component: () => import('@/views/NewPageView.vue'),
  meta: { requiresAuth: true }
}
```

### 添加新 API

1. 在 `src/api/` 创建 API 文件
2. 使用 `request` 或 `requestForm` 工具
3. 在 `src/types/index.ts` 定义类型
4. 在 `src/api/index.ts` 导出

```typescript
// src/api/example.ts
import { request } from '@/utils/request'

export const getExample = () => {
  return request.get('/example')
}
```

### 添加全局组件

在 `src/components/` 创建组件后，在 `src/main.ts` 中全局注册：

```typescript
import MyComponent from './components/MyComponent.vue'
app.component('MyComponent', MyComponent)
```

## 🧪 测试

运行单元测试：

```bash
npm test
```

测试文件位于 `tests/` 目录。

## 📝 常见问题

### 1. API 请求失败？
- 检查后端服务是否运行
- 确认 `VITE_API_BASE` 配置正确
- 查看浏览器控制台网络请求

### 2. 动画不流畅？
- 检查设备性能
- 确认浏览器支持 Web Animations API
- 系统会自动降级至基础 CSS 动画

### 3. 样式异常？
- 确保 Tailwind CSS 配置正确
- 检查 PostCSS 配置
- 清除浏览器缓存重新加载

### 4. 权限不足？
- 确认登录账户角色
- 管理员功能需要 `admin` 角色
- 检查 `localStorage` 中的用户信息

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

- 负责人：陈
- 邮箱：chenjh8181@gmail.com


---

**RAG 企业智能系统** - 让企业智能化更简单 🚀
