<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElCard, ElSkeleton, ElEmpty, ElButton, ElTag, ElTable, ElTableColumn, ElTabs, ElTabPane, ElUpload, ElProgress, ElDatePicker, ElSelect, ElOption } from 'element-plus'
import { 
  Shield,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  Upload,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  ClipboardList,
  DollarSign,
  Scale,
  Sparkles,
  RefreshCw,
  Activity,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Eye,
  Filter
} from 'lucide-vue-next'
import { multiAgentApi, type SecurityEvent } from '@/api/multi-agent'
import { auditApi } from '@/api/audit'
import type { AuditType, AuditDocument } from '@/api/audit'
import { useEnterpriseTheme } from '@/composables/useEnterpriseTheme'

const router = useRouter()
const { enterpriseTheme } = useEnterpriseTheme()
const primaryColor = computed(() => enterpriseTheme.value.primary_color)

const activeTab = ref('security')
const loading = ref(true)

const securityEvents = ref<SecurityEvent[]>([])
const securityStats = ref<{
  total_events: number
  by_severity: Record<string, number>
  by_type: Record<string, number>
  recent_trends: Array<{ date: string; count: number }>
} | null>(null)

const selectedSeverity = ref<string>('all')
const selectedDateRange = ref<[Date, Date] | null>(null)

const selectedFiles = ref<File[]>([])
const selectedAuditType = ref<AuditType>('comprehensive')
const isUploading = ref(false)
const uploadResult = ref<{ success: boolean; taskId?: string; error?: string } | null>(null)
const isDragging = ref(false)

const auditTypes = [
  { value: 'financial', label: '财务审查', icon: DollarSign, description: '资产负债表、利润表、现金流量表', color: 'from-green-500 to-emerald-600' },
  { value: 'tax', label: '税务审查', icon: ClipboardList, description: '税务合规性、税收风险', color: 'from-emerald-500 to-teal-600' },
  { value: 'legal', label: '法务审查', icon: Scale, description: '合同风险、法律合规', color: 'from-blue-500 to-indigo-600' },
  { value: 'compliance', label: '合规审查', icon: Sparkles, description: '全面合规性检查', color: 'from-orange-500 to-red-600' },
]

const severityColors = {
  low: { bg: 'bg-emerald-100', text: 'text-emerald-700', icon: ShieldCheck },
  medium: { bg: 'bg-yellow-100', text: 'text-yellow-700', icon: AlertTriangle },
  high: { bg: 'bg-orange-100', text: 'text-orange-700', icon: ShieldAlert },
  critical: { bg: 'bg-red-100', text: 'text-red-700', icon: ShieldX },
}

const eventTypeLabels: Record<string, string> = {
  permission_denied: '权限拒绝',
  authentication_failure: '认证失败',
  suspicious_activity: '可疑活动',
  data_access: '数据访问',
  configuration_change: '配置变更',
  system_error: '系统错误',
}

const filteredEvents = computed(() => {
  let events = securityEvents.value
  if (selectedSeverity.value !== 'all') {
    events = events.filter(e => e.severity === selectedSeverity.value)
  }
  return events
})

const securityOverview = computed(() => {
  if (!securityStats.value) return null
  const { by_severity, total_events } = securityStats.value
  return [
    { label: '总计事件', value: total_events, icon: Activity, color: '#409eff' },
    { label: '低风险', value: by_severity.low || 0, icon: ShieldCheck, color: '#67c23a' },
    { label: '中风险', value: by_severity.medium || 0, icon: AlertTriangle, color: '#e6a23c' },
    { label: '高风险', value: by_severity.high || 0, icon: ShieldAlert, color: '#f56c6c' },
    { label: '严重', value: by_severity.critical || 0, icon: ShieldX, color: '#f56c6c' },
  ]
})

const getSeverityIcon = (severity: string) => {
  const icons: Record<string, any> = {
    low: ShieldCheck,
    medium: AlertTriangle,
    high: ShieldAlert,
    critical: ShieldX,
  }
  return icons[severity] || Shield
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

const loadSecurityData = async () => {
  try {
    const [events, stats] = await Promise.all([
      multiAgentApi.getSecurityEvents(),
      multiAgentApi.getSecurityStats(),
    ])
    securityEvents.value = events
    securityStats.value = stats
  } catch (error) {
    console.error('加载安全数据失败:', error)
  }
}

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  addFiles(Array.from(target.files || []))
}

const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  isDragging.value = true
}

const handleDragLeave = () => {
  isDragging.value = false
}

const handleDrop = (event: DragEvent) => {
  event.preventDefault()
  isDragging.value = false
  addFiles(Array.from(event.dataTransfer?.files || []))
}

const addFiles = (files: File[]) => {
  const validTypes = ['.pdf', '.xlsx', '.xls', '.docx', '.doc']
  files.forEach(file => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (validTypes.includes(ext)) {
      if (!selectedFiles.value.find(f => f.name === file.name)) {
        selectedFiles.value.push(file)
      }
    }
  })
}

const removeFile = (index: number) => {
  selectedFiles.value.splice(index, 1)
}

const uploadAudit = async () => {
  if (selectedFiles.value.length === 0) return
  isUploading.value = true
  uploadResult.value = null
  
  try {
    const file = selectedFiles.value[0]
    const result = await auditApi.uploadAuditDocument(file, selectedAuditType.value)
    uploadResult.value = { success: true, taskId: result.task_id }
    selectedFiles.value = []
  } catch (error: any) {
    uploadResult.value = { success: false, error: error.message }
  } finally {
    isUploading.value = false
  }
}

const goToAuditResult = (taskId: string) => {
  router.push(`/audit/result/${taskId}`)
}

onMounted(() => {
  loadSecurityData()
})
</script>

<template>
  <div class="system-audit min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
    <div class="mb-6">
      <div class="flex items-center gap-4">
        <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg">
          <Shield :size="28" class="text-white" />
        </div>
        <div>
          <h1 class="text-3xl font-bold text-slate-900">系统审计中心</h1>
          <p class="text-slate-600">统一管理安全审计和合规审查</p>
        </div>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="audit-tabs">
      <el-tab-pane label="安全监控" name="security">
        <template #label>
          <div class="flex items-center gap-2">
            <Shield :size="16" />
            <span>安全监控</span>
          </div>
        </template>
        
        <div class="space-y-6">
          <!-- Security Overview Cards -->
          <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
            <el-card 
              v-for="(stat, index) in securityOverview" 
              :key="index"
              class="stat-card"
              :body-style="{ padding: '16px' }"
            >
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-sm text-slate-500">{{ stat.label }}</p>
                  <p class="text-2xl font-bold" :style="{ color: stat.color }">
                    <el-skeleton v-if="loading" animated :rows="0" />
                    <span v-else>{{ stat.value }}</span>
                  </p>
                </div>
                <div 
                  class="w-10 h-10 rounded-lg flex items-center justify-center"
                  :style="{ backgroundColor: `${stat.color}15` }"
                >
                  <component :is="stat.icon" :size="20" :style="{ color: stat.color }" />
                </div>
              </div>
            </el-card>
          </div>

          <!-- Filters -->
          <el-card :body-style="{ padding: '16px' }">
            <div class="flex flex-wrap items-center gap-4">
              <el-select v-model="selectedSeverity" placeholder="风险等级" clearable style="width: 140px">
                <el-option value="all" label="全部" />
                <el-option value="low" label="低风险" />
                <el-option value="medium" label="中风险" />
                <el-option value="high" label="高风险" />
                <el-option value="critical" label="严重" />
              </el-select>
              
              <el-date-picker
                v-model="selectedDateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                style="width: 260px"
              />
              
              <el-button type="primary" @click="loadSecurityData">
                <RefreshCw :size="14" class="mr-1" />
                刷新
              </el-button>
            </div>
          </el-card>

          <!-- Security Events Table -->
          <el-card :body-style="{ padding: '0' }">
            <template #header>
              <div class="flex items-center justify-between">
                <span class="text-lg font-semibold text-slate-800">安全事件列表</span>
                <el-tag type="info">{{ filteredEvents.length }} 条记录</el-tag>
              </div>
            </template>
            
            <el-table 
              :data="filteredEvents" 
              style="width: 100%"
              v-loading="loading"
              :header-cell-style="{ backgroundColor: '#f8fafc', color: '#475569' }"
            >
              <el-table-column prop="timestamp" label="时间" width="160">
                <template #default="{ row }">
                  <span class="text-sm text-slate-600">{{ formatTime(row.timestamp) }}</span>
                </template>
              </el-table-column>
              
              <el-table-column prop="event_type" label="事件类型" width="140">
                <template #default="{ row }">
                  <span class="text-slate-700">{{ eventTypeLabels[row.event_type] || row.event_type }}</span>
                </template>
              </el-table-column>
              
              <el-table-column prop="severity" label="风险等级" width="120">
                <template #default="{ row }">
                  <div class="flex items-center gap-2">
                    <component 
                      :is="getSeverityIcon(row.severity)" 
                      :size="16" 
                      :class="severityColors[row.severity]?.text"
                    />
                    <el-tag 
                      size="small" 
                      :class="[severityColors[row.severity]?.bg, severityColors[row.severity]?.text]"
                    >
                      {{ row.severity }}
                    </el-tag>
                  </div>
                </template>
              </el-table-column>
              
              <el-table-column prop="description" label="描述" min-width="200">
                <template #default="{ row }">
                  <span class="text-slate-600">{{ row.description }}</span>
                </template>
              </el-table-column>
              
              <el-table-column prop="ip_address" label="IP地址" width="140">
                <template #default="{ row }">
                  <span class="text-slate-500 font-mono text-sm">{{ row.ip_address || '-' }}</span>
                </template>
              </el-table-column>
              
              <el-table-column label="操作" width="100" fixed="right">
                <template #default="{ row }">
                  <el-button type="primary" text size="small">
                    <Eye :size="14" class="mr-1" />
                    详情
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
      </el-tab-pane>

      <el-tab-pane label="合规审计" name="compliance">
        <template #label>
          <div class="flex items-center gap-2">
            <ClipboardList :size="16" />
            <span>合规审计</span>
          </div>
        </template>
        
        <div class="space-y-6">
          <!-- Audit Type Selection -->
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <el-card 
              v-for="type in auditTypes" 
              :key="type.value"
              :class="[
                'audit-type-card cursor-pointer transition-all',
                selectedAuditType === type.value ? 'ring-2 ring-offset-2' : ''
              ]"
              :style="selectedAuditType === type.value ? { ringColor: primaryColor } : {}"
              :body-style="{ padding: '20px' }"
              @click="selectedAuditType = type.value as AuditType"
            >
              <div class="flex items-start gap-3">
                <div :class="['w-12 h-12 rounded-xl bg-gradient-to-br flex items-center justify-center', type.color]">
                  <component :is="type.icon" :size="24" class="text-white" />
                </div>
                <div class="flex-1">
                  <h3 class="font-semibold text-slate-800">{{ type.label }}</h3>
                  <p class="text-sm text-slate-500 mt-1">{{ type.description }}</p>
                </div>
                <CheckCircle 
                  v-if="selectedAuditType === type.value" 
                  :size="20" 
                  class="text-emerald-500"
                />
              </div>
            </el-card>
          </div>

          <!-- Upload Area -->
          <el-card :body-style="{ padding: '0' }">
            <div class="p-6">
              <h3 class="text-lg font-semibold text-slate-800 mb-4">上传审计文档</h3>
              
              <div 
                :class="[
                  'border-2 border-dashed rounded-xl p-8 text-center transition-colors',
                  isDragging ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 hover:border-slate-400'
                ]"
                @dragover="handleDragOver"
                @dragleave="handleDragLeave"
                @drop="handleDrop"
              >
                <Upload :size="48" class="mx-auto text-slate-400 mb-4" />
                <p class="text-slate-600 mb-2">拖拽文件到此处，或</p>
                <label class="cursor-pointer">
                  <span class="text-indigo-600 hover:text-indigo-700 font-medium">点击选择文件</span>
                  <input type="file" class="hidden" accept=".pdf,.xlsx,.xls,.docx,.doc" @change="handleFileSelect" />
                </label>
                <p class="text-xs text-slate-400 mt-2">支持 PDF、Excel、Word 格式</p>
              </div>

              <!-- Selected Files -->
              <div v-if="selectedFiles.length > 0" class="mt-4 space-y-2">
                <div 
                  v-for="(file, index) in selectedFiles" 
                  :key="index"
                  class="flex items-center justify-between p-3 bg-slate-50 rounded-lg"
                >
                  <div class="flex items-center gap-3">
                    <FileText :size="20" class="text-slate-500" />
                    <div>
                      <p class="text-slate-800">{{ file.name }}</p>
                      <p class="text-xs text-slate-500">{{ (file.size / 1024).toFixed(1) }} KB</p>
                    </div>
                  </div>
                  <el-button type="danger" text size="small" @click="removeFile(index)">
                    删除
                  </el-button>
                </div>
              </div>

              <!-- Upload Result -->
              <div v-if="uploadResult" class="mt-4">
                <el-alert
                  :type="uploadResult.success ? 'success' : 'error'"
                  :title="uploadResult.success ? '上传成功' : uploadResult.error"
                  show-icon
                >
                  <template #default>
                    <span v-if="uploadResult.success">
                      任务ID: {{ uploadResult.taskId }}
                      <el-button type="primary" text size="small" @click="goToAuditResult(uploadResult!.taskId!)">
                        查看结果
                      </el-button>
                    </span>
                  </template>
                </el-alert>
              </div>

              <!-- Upload Button -->
              <div class="mt-6 flex justify-end">
                <el-button 
                  type="primary" 
                  size="large" 
                  :loading="isUploading"
                  :disabled="selectedFiles.length === 0"
                  @click="uploadAudit"
                >
                  <Upload :size="16" class="mr-2" />
                  开始审计
                </el-button>
              </div>
            </div>
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.system-audit {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.stat-card {
  border-radius: 12px;
  border: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.audit-type-card {
  border-radius: 12px;
  border: 2px solid transparent;
  transition: all 0.3s ease;
}

.audit-type-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

:deep(.el-tabs__item) {
  font-size: 15px;
  padding: 0 20px;
}

:deep(.el-tabs__item.is-active) {
  color: v-bind(primaryColor);
}

:deep(.el-tabs__active-bar) {
  background-color: v-bind(primaryColor);
}
</style>
