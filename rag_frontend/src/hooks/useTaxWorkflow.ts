/**
 * 税务提交流工作流 Hook

提供工作流状态管理和 SSE 实时推送功能
 */

import { ref, computed, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import type {
  WorkflowEvent,
  WorkflowStep,
  TaxWorkflowState,
  WorkflowHistoryItem,
  HumanReviewRequestData
} from '@/types/tax-workflow'
import {
  WorkflowEventType,
  WorkflowStepStatus,
  WORKFLOW_STEPS
} from '@/types/tax-workflow'

export const useTaxWorkflow = () => {
  const workflowState = ref<TaxWorkflowState | null>(null)
  const history = ref<WorkflowHistoryItem[]>([])
  const isConnected = ref(false)
  const eventSource = ref<EventSource | null>(null)
  
  const currentStep = computed(() => workflowState.value?.currentStep || 0)
  const isRunning = computed(() => workflowState.value?.status === 'running')
  const isCompleted = computed(() => workflowState.value?.status === 'completed')
  const isFailed = computed(() => workflowState.value?.status === 'failed')
  const error = computed(() => workflowState.value?.error)
  
  const steps = computed<WorkflowStep[]>(() => {
    if (!workflowState.value) {
      return WORKFLOW_STEPS.map((step, index) => ({
        name: step.name,
        number: index + 1,
        status: WorkflowStepStatus.PENDING,
        label: step.label,
        description: step.description
      } as WorkflowStep))
    }
    
    return workflowState.value.steps
  })
  
  const humanReviewRequest = computed(() => workflowState.value?.humanReviewRequest)
  const hasHumanReviewRequest = computed(() => {
    const request = humanReviewRequest.value
    return request && request.status === 'pending'
  })
  
  const initWorkflow = (workflowId: string, sessionId: string) => {
    workflowState.value = {
      workflowId,
      sessionId,
      status: 'idle',
      currentStep: 0,
      totalSteps: WORKFLOW_STEPS.length,
      steps: WORKFLOW_STEPS.map((step, index) => ({
        name: step.name,
        number: index + 1,
        status: WorkflowStepStatus.PENDING,
        label: step.label,
        description: step.description
      })),
      startTime: new Date().toISOString()
    }
    
    history.value = []
  }
  
  const updateStepStatus = (
    stepName: string,
    status: WorkflowStepStatus,
    data?: Record<string, any>,
    error?: string
  ) => {
    if (!workflowState.value) return
    
    const stepIndex = workflowState.value.steps.findIndex(s => s.name === stepName)
    if (stepIndex === -1) return
    
    const step = workflowState.value.steps[stepIndex]
    step.status = status
    
    if (status === WorkflowStepStatus.RUNNING) {
      step.startTime = new Date().toISOString()
      workflowState.value.currentStep = step.number
    } else if (status === WorkflowStepStatus.COMPLETED || status === WorkflowStepStatus.FAILED) {
      step.endTime = new Date().toISOString()
      if (step.startTime) {
        step.duration = new Date(step.endTime).getTime() - new Date(step.startTime).getTime()
      }
    }
    
    if (data) {
      step.data = data
    }
    
    if (error) {
      step.error = error
    }
    
    workflowState.value.status = workflowState.value.steps.some(s => s.status === WorkflowStepStatus.FAILED)
      ? 'failed'
      : 'running'
  }
  
  const addHistoryItem = (item: WorkflowHistoryItem) => {
    history.value.push(item)
    
    if (item.severity === 'error') {
      ElMessage.error({
        message: item.message,
        duration: 5000
      })
    } else if (item.severity === 'warning') {
      ElMessage.warning({
        message: item.message,
        duration: 3000
      })
    }
  }
  
  const handleEvent = (event: WorkflowEvent) => {
    switch (event.event_type) {
      case WorkflowEventType.STARTED:
        if (workflowState.value) {
          workflowState.value.status = 'running'
          addHistoryItem({
            event,
            message: '税务提交流工作流已启动',
            severity: 'info'
          })
        }
        break
        
      case WorkflowEventType.STEP_STARTED:
        if (event.step_name) {
          updateStepStatus(event.step_name, WorkflowStepStatus.RUNNING, event.data)
          addHistoryItem({
            event,
            stepName: event.step_name,
            stepNumber: event.step_number,
            message: `开始执行: ${getStepLabel(event.step_name)}`,
            severity: 'info'
          })
        }
        break
        
      case WorkflowEventType.STEP_COMPLETED:
        if (event.step_name) {
          updateStepStatus(event.step_name, WorkflowStepStatus.COMPLETED, event.data)
          addHistoryItem({
            event,
            stepName: event.step_name,
            stepNumber: event.step_number,
            message: `完成: ${getStepLabel(event.step_name)}`,
            severity: 'success'
          })
          
          if (event.step_name === 'assess_risk' && event.data?.high_risk_count > 0) {
            addHistoryItem({
              event,
              stepName: event.step_name,
              message: `检测到 ${event.data.high_risk_count} 个高风险项`,
              severity: 'warning'
            })
          }
        }
        break
        
      case WorkflowEventType.STEP_FAILED:
        if (event.step_name) {
          updateStepStatus(event.step_name, WorkflowStepStatus.FAILED, undefined, event.error)
          workflowState.value!.error = event.error
          addHistoryItem({
            event,
            stepName: event.step_name,
            stepNumber: event.step_number,
            message: `失败: ${getStepLabel(event.step_name)} - ${event.error}`,
            severity: 'error'
          })
        }
        break
        
      case WorkflowEventType.STEP_WARNING:
        if (event.step_name) {
          updateStepStatus(event.step_name, WorkflowStepStatus.WARNING)
          addHistoryItem({
            event,
            stepName: event.step_name,
            stepNumber: event.step_number,
            message: `警告: ${event.error}`,
            severity: 'warning'
          })
        }
        break
        
      case WorkflowEventType.HUMAN_REVIEW_REQUIRED:
        if (workflowState.value) {
          updateStepStatus('human_review', WorkflowStepStatus.WAITING_REVIEW)
          workflowState.value.humanReviewRequest = {
            reviewId: event.data.review_id,
            reason: event.data.reason,
            requestedAt: event.timestamp,
            requestedBy: event.data.requested_by || '系统',
            status: 'pending',
            riskItems: event.data.risk_items || [],
            reviewData: event.data
          }
          addHistoryItem({
            event,
            stepName: 'human_review',
            message: '需要人工审核',
            severity: 'warning'
          })
        }
        break
        
      case WorkflowEventType.COMPLETED:
        if (workflowState.value) {
          workflowState.value.status = 'completed'
          workflowState.value.endTime = new Date().toISOString()
          if (workflowState.value.startTime) {
            workflowState.value.duration =
              new Date(workflowState.value.endTime).getTime() -
              new Date(workflowState.value.startTime).getTime()
          }
          addHistoryItem({
            event,
            message: '税务提交流工作流已完成',
            severity: 'success'
          })
        }
        break
        
      case WorkflowEventType.FAILED:
        if (workflowState.value) {
          workflowState.value.status = 'failed'
          workflowState.value.error = event.error
          workflowState.value.endTime = new Date().toISOString()
          addHistoryItem({
            event,
            message: `工作流失败: ${event.error}`,
            severity: 'error'
          })
        }
        break
        
      case WorkflowEventType.HEARTBEAT:
        break
    }
  }
  
  const getStepLabel = (stepName: string): string => {
    const step = WORKFLOW_STEPS.find(s => s.name === stepName)
    return step?.label || stepName
  }
  
  const connect = (workflowId: string) => {
    if (eventSource.value) {
      eventSource.value.close()
    }
    
    const token = localStorage.getItem('rag_token')
    const url = `/api/v1/workflow-events/stream/${workflowId}`
    
    eventSource.value = new EventSource(url, {
      withCredentials: true
    } as EventSourceInit)
    
    eventSource.value.onopen = () => {
      isConnected.value = true
      console.log('📡 SSE 连接已建立')
    }
    
    eventSource.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WorkflowEvent
        handleEvent(data)
      } catch (error) {
        console.error('❌ 解析 SSE 事件失败:', error)
      }
    }
    
    eventSource.value.onerror = (error) => {
      console.error('❌ SSE 连接错误:', error)
      isConnected.value = false
      
      setTimeout(() => {
        if (isConnected.value === false && workflowState.value?.status === 'running') {
          console.log('🔄 尝试重新连接...')
          connect(workflowId)
        }
      }, 3000)
    }
  }
  
  const disconnect = () => {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
      isConnected.value = false
      console.log('📡 SSE 连接已关闭')
    }
  }
  
  const submitHumanReview = async (reviewId: string, approved: boolean, comments?: string) => {
    try {
      const response = await fetch('/api/v1/human-review/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('rag_token')}`
        },
        body: JSON.stringify({
          review_id: reviewId,
          approved,
          comments
        })
      })
      
      if (!response.ok) {
        throw new Error('提交审核结果失败')
      }
      
      if (workflowState.value) {
        updateStepStatus('human_review', WorkflowStepStatus.COMPLETED)
        workflowState.value.humanReviewRequest!.status = approved ? 'approved' : 'rejected'
      }
      
      ElMessage.success({
        message: approved ? '审核已通过' : '审核已拒绝',
        duration: 3000
      })
      
    } catch (error) {
      ElMessage.error({
        message: '提交审核结果失败',
        duration: 3000
      })
      throw error
    }
  }
  
  onUnmounted(() => {
    disconnect()
  })
  
  return {
    workflowState,
    history,
    steps,
    currentStep,
    isRunning,
    isCompleted,
    isFailed,
    error,
    isConnected,
    humanReviewRequest,
    hasHumanReviewRequest,
    initWorkflow,
    connect,
    disconnect,
    submitHumanReview
  }
}
