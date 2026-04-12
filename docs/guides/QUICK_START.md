# 🚀 税务提交工作流 - 快速参考

## 组件使用速查表

### 1. 最简集成 (一行代码)

```vue
<template>
  <TaxSubmissionWorkflow ref="workflow" />
  <el-button @click="start">开始提交</el-button>
</template>

<script setup>
import TaxSubmissionWorkflow from '@/components/TaxSubmissionWorkflow.vue'
const workflow = ref()

const start = () => {
  workflow.value.startWorkflow(`tax-${Date.now()}`, `session-${Date.now()}`)
}
</script>
```

### 2. 监听工作流事件

```vue
<TaxSubmissionWorkflow
  ref="workflow"
  @start="onStart"
  @complete="onComplete"
  @cancel="onCancel"
  @error="onError"
/>
```

### 3. 获取工作流状态

```typescript
const workflow = ref()
const { workflowState, isRunning, isCompleted, isFailed } = workflow.value

// 在模板中
<div v-if="workflow?.isRunning">处理中...</div>
<div v-if="workflow?.isCompleted">已完成！</div>
```

### 4. 手动处理审核

```typescript
const { hasHumanReviewRequest, humanReviewRequest } = useTaxWorkflow()

watch(hasHumanReviewRequest, (needsReview) => {
  if (needsReview) {
    // 显示自定义审核界面
    showCustomReviewDialog()
  }
})

// 提交审核
await submitHumanReview({
  decision: 'approved',
  comment: '审核通过'
})
```

### 5. 查看详细数据

```typescript
const { workflowState } = useTaxWorkflow()

// 税务计算结果
workflowState.value?.taxCalculations

// 风险评估
workflowState.value?.riskAssessment

// 步骤详情
workflowState.value?.steps

// 历史记录
history.value
```

## API 端点

### SSE 流
```
GET /api/v1/workflow-events/stream/{workflow_id}
```

### 获取状态
```
GET /api/v1/workflow-events/state/{workflow_id}
```

### 获取历史
```
GET /api/v1/workflow-events/history/{workflow_id}
```

## 事件类型

| 事件 | 说明 |
|------|------|
| `workflow_started` | 工作流启动 |
| `step_started` | 步骤开始 |
| `step_completed` | 步骤完成 |
| `step_failed` | 步骤失败 |
| `step_warning` | 步骤警告 |
| `human_review_required` | 需要人工审核 |
| `human_review_completed` | 审核完成 |
| `workflow_completed` | 工作流完成 |
| `workflow_failed` | 工作流失败 |
| `heartbeat` | 心跳 |

## 步骤状态

| 状态 | 颜色 | 说明 |
|------|------|------|
| `pending` | 灰 | 待处理 |
| `running` | 蓝 | 运行中 |
| `completed` | 绿 | 已完成 |
| `failed` | 红 | 失败 |
| `warning` | 橙 | 警告 |
| `waiting_review` | 紫 | 等待审核 |

## 工作流步骤

```
1. 数据验证
   ↓
2. 获取财务数据
   ↓
3. 税务计算
   ↓
4. 风险评估
   ↓
   ├─ 高风险 → 人工审核
   └─ 低风险 → 保存结果
```

## 常用代码片段

### 重试失败的工作流
```typescript
const handleRetry = () => {
  const { workflowId, sessionId } = workflow.value.workflowState
  workflow.value.disconnect()
  workflow.value.startWorkflow(workflowId, sessionId)
}
```

### 复制原始数据
```typescript
const copyRawData = async () => {
  const raw = JSON.stringify(workflowState.value, null, 2)
  await navigator.clipboard.writeText(raw)
  ElMessage.success('已复制')
}
```

### 格式化金额
```typescript
const formatMoney = (amount: number) => {
  return `¥${amount.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`
}
```

### 计算进度
```typescript
const progress = computed(() => {
  const completed = steps.value.filter(s => 
    s.status === 'completed' || s.status === 'failed'
  ).length
  return Math.round((completed / steps.value.length) * 100)
})
```

## 样式变量

```css
:root {
  --el-color-primary: #409EFF;
  --el-color-success: #67C23A;
  --el-color-warning: #E6A23C;
  --el-color-danger: #F56C6C;
  --el-color-info: #909399;
}
```

## 动画效果

- **运行中**: `<Loading />` 图标旋转
- **待审核**: 脉冲动画 (pulse)
- **完成**: 绿色渐变
- **失败**: 红色高亮

## 快捷键

- `Ctrl + C`: 复制数据
- `Ctrl + R`: 重试
- `Esc`: 关闭弹窗

## 调试技巧

### 查看 SSE 连接状态
```typescript
const { isConnected } = useTaxWorkflow()
console.log('SSE 连接:', isConnected.value)
```

### 查看所有事件
```typescript
watch(workflowState, (state) => {
  console.log('状态更新:', state)
})
```

### 查看历史记录
```typescript
watch(history, (items) => {
  console.log('历史:', items)
}, { deep: true })
```

## 错误排查

| 问题 | 原因 | 解决 |
|------|------|------|
| SSE 连接失败 | 网络问题 | 检查网络和认证 |
| 审核按钮不可用 | 状态不对 | 确保 `needs_review` 为 true |
| 进度条不更新 | SSE 断开 | 检查连接状态 |
| 数据不显示 | 未传数据 | 检查 API 返回 |

## 性能优化

1. **避免深度监听**
```typescript
// ❌ 不好
watch(workflowState, () => {}, { deep: true })

// ✅ 好
watch(() => workflowState.value.status, ...)
```

2. **使用 computed**
```typescript
// ❌ 不好
const isRunning = workflowState.value?.status === 'running'

// ✅ 好
const isRunning = computed(() => 
  workflowState.value?.status === 'running'
)
```

3. **及时清理**
```typescript
onUnmounted(() => {
  disconnect()
})
```

## 最佳实践

1. ✅ 使用 `ref` 获取组件实例
2. ✅ 在 `onUnmounted` 清理连接
3. ✅ 监听 `error` 事件处理错误
4. ✅ 使用 TypeScript 类型定义
5. ✅ 遵循单一职责原则
6. ✅ 保持组件纯净，不处理复杂逻辑

---

**版本**: 1.0.0  
**更新**: 2026-04-09
