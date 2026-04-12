# 税务提交工作流集成指南

## 组件概览

本指南将帮助你在现有页面中集成税务提交流工作流 UI 组件。

## 组件列表

### 1. TaxSubmissionWorkflow.vue
**位置**: `src/components/TaxSubmissionWorkflow.vue`
**功能**: 主集成组件，整合所有子组件，提供完整的税务提交工作流功能
**用途**: 用于税务提交页面，作为工作流的主容器

### 2. TaxWorkflowViewer.vue
**位置**: `src/components/TaxWorkflowViewer.vue`
**功能**: 美观的步骤条和状态显示组件
**用途**: 显示工作流进度、各步骤状态、执行历史

### 3. HumanReviewDialog.vue
**位置**: `src/components/HumanReviewDialog.vue`
**功能**: 人工审核模态框
**用途**: 当工作流需要人工审核时，弹出审核界面

### 4. TaxWorkflowStepData.vue
**位置**: `src/components/TaxWorkflowStepData.vue`
**功能**: 步骤数据展示组件
**用途**: 显示每个步骤的输入输出数据

### 5. TaxWorkflowCalculations.vue
**位置**: `src/components/TaxWorkflowCalculations.vue`
**功能**: 税务计算结果展示组件
**用途**: 展示税务计算的各项数据

### 6. TaxWorkflowRisk.vue
**位置**: `src/components/TaxWorkflowRisk.vue`
**功能**: 风险评估展示组件
**用途**: 展示风险评估结果和建议

### 7. useTaxWorkflow.ts
**位置**: `src/hooks/useTaxWorkflow.ts`
**功能**: 核心状态管理 Hook
**用途**: 管理工作流状态、处理 SSE 连接、事件处理

### 8. tax-workflow.ts
**位置**: `src/types/tax-workflow.ts`
**功能**: TypeScript 类型定义
**用途**: 定义所有类型和接口

## 集成步骤

### 步骤 1: 导入组件

在你需要使用税务提交流工作流的 Vue 页面中：

```vue
<template>
  <div class="tax-submission-page">
    <TaxSubmissionWorkflow
      ref="workflowRef"
      @start="handleWorkflowStart"
      @cancel="handleWorkflowCancel"
      @complete="handleWorkflowComplete"
      @error="handleWorkflowError"
    />

    <el-button type="primary" @click="startTaxSubmission">
      开始税务提交
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import TaxSubmissionWorkflow from '@/components/TaxSubmissionWorkflow.vue'

const workflowRef = ref()

const startTaxSubmission = () => {
  // 生成唯一的工作流 ID 和会话 ID
  const workflowId = `tax-${Date.now()}`
  const sessionId = `session-${Date.now()}`

  // 启动工作流
  workflowRef.value.startWorkflow(workflowId, sessionId)
}

const handleWorkflowStart = (data: { workflowId: string; sessionId: string }) => {
  console.log('工作流已启动:', data)
}

const handleWorkflowCancel = () => {
  console.log('工作流已取消')
}

const handleWorkflowComplete = (data: any) => {
  console.log('工作流已完成:', data)
}

const handleWorkflowError = (error: string) => {
  console.error('工作流错误:', error)
}
</script>
```

### 步骤 2: 使用 TypeScript 类型

确保在你的 TypeScript 代码中导入正确的类型：

```typescript
import {
  WorkflowEventType,
  WorkflowStepStatus,
  WorkflowEvent,
  WorkflowStep,
  TaxWorkflowState,
  HumanReviewRequestData,
  RiskItem,
  TaxCalculationResult,
  WORKFLOW_STEPS
} from '@/types/tax-workflow'
```

### 步骤 3: 自定义工作流 Hook

如果需要更多自定义功能，可以直接使用 `useTaxWorkflow` hook：

```typescript
import { useTaxWorkflow } from '@/hooks/useTaxWorkflow'

const {
  workflowState,    // 当前工作流状态
  history,         // 执行历史
  steps,           // 所有步骤的状态
  isRunning,       // 是否正在运行
  isCompleted,     // 是否已完成
  isFailed,        // 是否失败
  error,           // 错误信息
  isConnected,     // SSE 连接状态
  humanReviewRequest,  // 人工审核请求
  hasHumanReviewRequest,  // 是否有待审核项
  initWorkflow,    // 初始化工作流
  connect,         // 连接 SSE
  disconnect,      // 断开 SSE
  submitHumanReview  // 提交审核结果
} = useTaxWorkflow()
```

## SSE API 端点

### 后端 API

后端提供了以下 SSE API 端点：

1. **SSE 流式推送** (已注册)
   - URL: `/api/v1/workflow-events/stream/{workflow_id}`
   - 方法: GET
   - 功能: 实时推送工作流状态更新
   - 认证: 需要登录用户

2. **获取当前状态**
   - URL: `/api/v1/workflow-events/state/{workflow_id}`
   - 方法: GET
   - 功能: 获取工作流当前状态

3. **获取历史事件**
   - URL: `/api/v1/workflow-events/history/{workflow_id}`
   - 方法: GET
   - 功能: 获取工作流历史事件列表

## 事件类型

工作流支持以下事件类型：

```typescript
enum WorkflowEventType {
  STARTED = 'workflow_started',           // 工作流启动
  STEP_STARTED = 'step_started',         // 步骤开始
  STEP_COMPLETED = 'step_completed',     // 步骤完成
  STEP_FAILED = 'step_failed',           // 步骤失败
  STEP_WARNING = 'step_warning',         // 步骤警告
  STATUS_CHANGED = 'status_changed',     // 状态变更
  DATA_UPDATED = 'data_updated',          // 数据更新
  HUMAN_REVIEW_REQUIRED = 'human_review_required',  // 需要人工审核
  HUMAN_REVIEW_COMPLETED = 'human_review_completed',  // 人工审核完成
  COMPLETED = 'workflow_completed',       // 工作流完成
  FAILED = 'workflow_failed',            // 工作流失败
  HEARTBEAT = 'heartbeat'                // 心跳
}
```

## 步骤定义

工作流包含以下步骤：

```typescript
const WORKFLOW_STEPS = [
  { name: 'validate_submission', label: '数据验证', description: '验证提交数据的完整性和合法性' },
  { name: 'fetch_financial_data', label: '获取财务数据', description: '从数据库获取财务数据' },
  { name: 'calculate_taxes', label: '税务计算', description: '执行税务计算' },
  { name: 'assess_risk', label: '风险评估', description: '评估税务风险' },
  { name: 'human_review', label: '人工审核', description: '高风险项需人工审核' },
  { name: 'save_submission', label: '保存结果', description: '保存税务分析结果' }
]
```

## 状态说明

### 工作流状态
- `idle`: 空闲状态
- `running`: 运行中
- `completed`: 已完成
- `failed`: 失败

### 步骤状态
- `pending`: 待处理
- `running`: 运行中
- `completed`: 已完成
- `failed`: 失败
- `warning`: 警告
- `waiting_review`: 等待审核

## 样式自定义

所有组件都使用 Element Plus 组件库，支持主题定制。

### 颜色方案
- 主色调: `#409EFF` (蓝色)
- 成功: `#67C23A` (绿色)
- 警告: `#E6A23C` (橙色)
- 危险: `#F56C6C` (红色)
- 信息: `#909399` (灰色)

### 动画效果
- 步骤运行中: 加载图标旋转动画
- 待审核: 脉冲动画
- 进度条: 渐变色动画

## 最佳实践

1. **错误处理**: 始终监听 `error` 事件，处理可能的错误
2. **重连机制**: SSE 自动重连已内置，无需额外处理
3. **状态持久化**: 如需持久化，考虑在 `complete` 事件中保存状态
4. **审核通知**: 有待审核项时会自动弹出通知
5. **清理资源**: 组件卸载时会自动断开 SSE 连接

## 常见问题

### Q: 如何处理人工审核？
A: 当 `hasHumanReviewRequest` 为 true 时，会弹出审核通知。点击"前往审核"按钮打开审核对话框。

### Q: 如何查看详细数据？
A: 点击"查看详情"按钮可以展开详细数据面板，包含步骤数据、计算结果、风险评估等。

### Q: 如何获取原始数据？
A: 在详情面板的"原始数据"标签页可以查看完整的 JSON 数据，并支持复制。

### Q: 如何自定义步骤？
A: 修改 `WORKFLOW_STEPS` 常量即可添加、删除或修改步骤。

## 示例代码

完整的集成示例：

```vue
<template>
  <div class="tax-submission-container">
    <el-page-header @back="goBack" content="税务提交" />

    <el-card class="workflow-card">
      <TaxSubmissionWorkflow
        ref="workflowRef"
        :workflow-id="workflowId"
        :session-id="sessionId"
        @start="handleStart"
        @cancel="handleCancel"
        @complete="handleComplete"
        @error="handleError"
      />
    </el-card>

    <div class="action-buttons" v-if="!workflowRef?.isRunning">
      <el-button type="primary" size="large" @click="submit">
        提交税务
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import TaxSubmissionWorkflow from '@/components/TaxSubmissionWorkflow.vue'

const router = useRouter()
const workflowRef = ref()
const workflowId = ref('')
const sessionId = ref('')

const submit = () => {
  workflowId.value = `tax-${Date.now()}`
  sessionId.value = `session-${Date.now()}`
  workflowRef.value.startWorkflow(workflowId.value, sessionId.value)
}

const handleStart = () => {
  ElMessage.success('税务提交流工作流已启动')
}

const handleCancel = () => {
  ElMessage.warning('工作流已取消')
}

const handleComplete = (data: any) => {
  ElMessage.success('税务提交已完成')
  router.push({ name: 'tax-reports' })
}

const handleError = (error: string) => {
  ElMessage.error(`错误: ${error}`)
}

const goBack = () => {
  router.back()
}
</script>
```

## 技术支持

如有问题，请检查：
1. 后端 SSE 端点是否正确注册
2. 网络连接是否正常
3. 用户是否已登录
4. 工作流 ID 和会话 ID 是否正确传递

---

**版本**: 1.0.0
**更新日期**: 2024-04-09
**作者**: 前端开发团队
