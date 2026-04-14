<template>
  <div class="system-overview p-6 bg-slate-50 min-h-screen">
    <div class="max-w-7xl mx-auto">
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-slate-800 mb-2">项目技术概览</h1>
        <p class="text-slate-600">展示系统架构、技术栈和项目规模等关键指标</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <el-card shadow="hover" :body-style="{ padding: '20px' }">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-slate-500 mb-1">系统状态</p>
              <p class="text-2xl font-bold" :class="systemStatusClass">
                {{ systemStatusText }}
              </p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center">
              <Activity :size="24" :class="systemStatusIconClass" />
            </div>
          </div>
        </el-card>

        <el-card shadow="hover" :body-style="{ padding: '20px' }">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-slate-500 mb-1">企业用户</p>
              <p class="text-2xl font-bold text-slate-800">{{ users.length }}</p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
              <Users :size="24" class="text-blue-600" />
            </div>
          </div>
        </el-card>

        <el-card shadow="hover" :body-style="{ padding: '20px' }">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-slate-500 mb-1">API 端点</p>
              <p class="text-2xl font-bold text-slate-800">44</p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center">
              <GitBranch :size="24" class="text-indigo-600" />
            </div>
          </div>
        </el-card>

        <el-card shadow="hover" :body-style="{ padding: '20px' }">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-slate-500 mb-1">专家智能体</p>
              <p class="text-2xl font-bold text-amber-600">6</p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-amber-100 flex items-center justify-center">
              <Clock :size="24" class="text-amber-600" />
            </div>
          </div>
        </el-card>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <el-card :body-style="{ padding: '20px' }">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-semibold text-slate-800">系统运行状态</span>
              <el-tag size="small" :type="systemTagType">
                {{ systemStatusText }}
              </el-tag>
            </div>
          </template>
          
          <div v-if="healthReport" class="space-y-4">
            <div v-for="component in healthReport.components" :key="component.name">
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm text-slate-600">{{ getComponentName(component.name) }}</span>
                <span class="text-sm font-medium" :class="getComponentStatusClass(component.status)">
                  {{ component.latency_ms ? `${component.latency_ms}ms` : getComponentStatusText(component.status) }}
                </span>
              </div>
              <el-progress 
                :percentage="getComponentPercentage(component.status)" 
                :stroke-width="8" 
                :color="getComponentProgressColor(component.status)" 
              />
            </div>
            
            <div class="mt-4 pt-4 border-t border-slate-200">
              <div class="flex items-center justify-between text-sm">
                <span class="text-slate-500">系统运行时间</span>
                <span class="font-medium text-slate-700">{{ getUptime() }}</span>
              </div>
            </div>
          </div>
          
          <div v-else-if="healthLoading" class="flex items-center justify-center py-8">
            <el-icon class="is-loading text-2xl text-slate-400">
              <Loading />
            </el-icon>
          </div>
          
          <div v-else class="text-center py-8 text-slate-500">
            暂无健康数据
          </div>
        </el-card>

        <el-card :body-style="{ padding: '20px' }">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-semibold text-slate-800">快捷入口</span>
            </div>
          </template>
          
          <div class="grid grid-cols-2 gap-4">
            <router-link to="/system-audit" class="no-underline">
              <div class="p-4 rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 transition-all cursor-pointer">
                <Shield :size="24" class="text-indigo-600 mb-2" />
                <h4 class="font-semibold text-slate-800 mb-1">系统审计</h4>
                <p class="text-xs text-slate-500">安全监控与合规审计</p>
              </div>
            </router-link>
            
            <router-link to="/agent-center" class="no-underline">
              <div class="p-4 rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 transition-all cursor-pointer">
                <Bot :size="24" class="text-indigo-600 mb-2" />
                <h4 class="font-semibold text-slate-800 mb-1">智能体中心</h4>
                <p class="text-xs text-slate-500">管理和配置 AI 智能体</p>
              </div>
            </router-link>
            
            <router-link to="/workflow" class="no-underline">
              <div class="p-4 rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 transition-all cursor-pointer">
                <GitBranch :size="24" class="text-indigo-600 mb-2" />
                <h4 class="font-semibold text-slate-800 mb-1">工作流总览</h4>
                <p class="text-xs text-slate-500">监控所有工作流状态</p>
              </div>
            </router-link>
            
            <router-link to="/review-center" class="no-underline">
              <div class="p-4 rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 transition-all cursor-pointer">
                <ListChecks :size="24" class="text-indigo-600 mb-2" />
                <h4 class="font-semibold text-slate-800 mb-1">审核中心</h4>
                <p class="text-xs text-slate-500">待审核任务管理</p>
              </div>
            </router-link>
          </div>
        </el-card>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <el-card :body-style="{ padding: '20px' }" class="lg:col-span-2">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-semibold text-slate-800">最近注册用户</span>
              <el-button type="primary" text size="small">查看全部</el-button>
            </div>
          </template>
          
          <el-table :data="recentUsers" style="width: 100%" v-if="recentUsers.length > 0">
            <el-table-column prop="created_at" label="注册时间" width="180">
              <template #default="{ row }">
                <span class="text-slate-600">{{ formatDate(row.created_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="full_name" label="姓名" width="120">
              <template #default="{ row }">
                <div class="flex items-center gap-2">
                  <div class="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
                    <span class="text-white text-xs font-semibold">{{ getInitials(row.full_name || row.email) }}</span>
                  </div>
                  <span class="text-slate-700">{{ row.full_name || row.email.split('@')[0] }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="company_position" label="职位" width="150">
              <template #default="{ row }">
                <span class="text-slate-700">{{ row.company_position || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '活跃' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_admin" label="角色" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_admin ? 'warning' : 'info'" size="small">
                  {{ row.is_admin ? '管理员' : '用户' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          
          <div v-else-if="usersLoading" class="flex items-center justify-center py-12">
            <el-icon class="is-loading text-2xl text-slate-400">
              <Loading />
            </el-icon>
          </div>
          
          <div v-else class="text-center py-12 text-slate-500">
            暂无用户数据
          </div>
        </el-card>

        <el-card :body-style="{ padding: '20px' }">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-semibold text-slate-800">项目技术统计</span>
            </div>
          </template>
          
          <div class="space-y-4">
            <div class="flex items-center justify-between p-3 rounded-lg bg-slate-50">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
                  <CheckCircle :size="20" class="text-emerald-600" />
                </div>
                <div>
                  <p class="text-sm font-medium text-slate-800">活跃用户</p>
                  <p class="text-xs text-slate-500">当前在线</p>
                </div>
              </div>
              <p class="text-xl font-bold text-slate-800">{{ activeUsersCount }}</p>
            </div>
            
            <div class="flex items-center justify-between p-3 rounded-lg bg-slate-50">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                  <PlayCircle :size="20" class="text-blue-600" />
                </div>
                <div>
                  <p class="text-sm font-medium text-slate-800">管理员</p>
                  <p class="text-xs text-slate-500">系统管理员</p>
                </div>
              </div>
              <p class="text-xl font-bold text-slate-800">{{ adminUsersCount }}</p>
            </div>
            
            <div class="flex items-center justify-between p-3 rounded-lg bg-slate-50">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
                  <Clock :size="20" class="text-amber-600" />
                </div>
                <div>
                  <p class="text-sm font-medium text-slate-800">后端模块</p>
                  <p class="text-xs text-slate-500">Python 文件</p>
                </div>
              </div>
              <p class="text-xl font-bold text-slate-800">403</p>
            </div>
            
            <div class="flex items-center justify-between p-3 rounded-lg bg-slate-50">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
                  <XCircle :size="20" class="text-red-600" />
                </div>
                <div>
                  <p class="text-sm font-medium text-slate-800">前端组件</p>
                  <p class="text-xs text-slate-500">Vue/TS 文件</p>
                </div>
              </div>
              <p class="text-xl font-bold text-slate-800">127</p>
            </div>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Activity, Users, GitBranch, Clock, Shield, Bot, ListChecks, CheckCircle, PlayCircle, XCircle } from 'lucide-vue-next'
import { ElIcon } from 'element-plus'
import 'element-plus/theme-chalk/el-icon.css'
import { useEnterpriseUsers } from '@/composables/useEnterpriseUsers'
import { useSystemHealth } from '@/composables/useSystemHealth'

const { 
  users, 
  loading: usersLoading, 
  getRecentUsers, 
  getActiveUsers, 
  getAdminUsers 
} = useEnterpriseUsers()

const { 
  healthReport, 
  loading: healthLoading, 
  getUptime, 
  getComponentByName,
  getOverallStatus 
} = useSystemHealth()

const recentUsers = computed(() => getRecentUsers(5))
const activeUsersCount = computed(() => getActiveUsers().length)
const adminUsersCount = computed(() => getAdminUsers().length)

const systemStatusText = computed(() => {
  const status = getOverallStatus()
  const statusMap = {
    healthy: '健康',
    degraded: '性能下降',
    unhealthy: '异常',
    unknown: '未知'
  }
  return statusMap[status as keyof typeof statusMap] || '未知'
})

const systemStatusClass = computed(() => {
  const status = getOverallStatus()
  const classMap = {
    healthy: 'text-emerald-600',
    degraded: 'text-amber-600',
    unhealthy: 'text-red-600',
    unknown: 'text-slate-500'
  }
  return classMap[status as keyof typeof classMap] || 'text-slate-500'
})

const systemStatusIconClass = computed(() => {
  const status = getOverallStatus()
  const classMap = {
    healthy: 'text-emerald-600',
    degraded: 'text-amber-600',
    unhealthy: 'text-red-600',
    unknown: 'text-slate-500'
  }
  return classMap[status as keyof typeof classMap] || 'text-slate-500'
})

const systemTagType = computed(() => {
  const status = getOverallStatus()
  const typeMap = {
    healthy: 'success',
    degraded: 'warning',
    unhealthy: 'danger',
    unknown: 'info'
  }
  return typeMap[status as keyof typeof typeMap] || 'info'
})

const getComponentName = (name: string) => {
  const nameMap = {
    database: '数据库',
    redis: 'Redis 缓存',
    llm_service: 'LLM 服务',
    storage: '对象存储',
    mcp_service: 'MCP 服务'
  }
  return nameMap[name as keyof typeof nameMap] || name
}

const getComponentStatusClass = (status: string) => {
  const classMap = {
    healthy: 'text-emerald-600',
    degraded: 'text-amber-600',
    unhealthy: 'text-red-600',
    unknown: 'text-slate-500'
  }
  return classMap[status as keyof typeof classMap] || 'text-slate-500'
}

const getComponentStatusText = (status: string) => {
  const textMap = {
    healthy: '正常',
    degraded: '性能下降',
    unhealthy: '异常',
    unknown: '未知'
  }
  return textMap[status as keyof typeof textMap] || status
}

const getComponentPercentage = (status: string) => {
  const percentageMap = {
    healthy: 100,
    degraded: 60,
    unhealthy: 20,
    unknown: 0
  }
  return percentageMap[status as keyof typeof percentageMap] || 0
}

const getComponentProgressColor = (status: string) => {
  const colorMap = {
    healthy: '#10b981',
    degraded: '#f59e0b',
    unhealthy: '#ef4444',
    unknown: '#94a3b8'
  }
  return colorMap[status as keyof typeof colorMap] || '#94a3b8'
}

const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const getInitials = (name: string) => {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}
</script>

<style scoped>
.system-overview {
  animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
