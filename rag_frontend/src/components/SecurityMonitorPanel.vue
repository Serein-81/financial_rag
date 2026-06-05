<template>
  <div class="security-monitor-panel">
    <!-- 概览统计 -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-white border border-slate-200 rounded-lg p-4">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
            <Users :size="24" class="text-blue-600" />
          </div>
          <div>
            <div class="text-sm text-slate-600">租户总数</div>
            <div class="text-2xl font-bold text-slate-900">{{ tenantStats?.total_tenants || 0 }}</div>
          </div>
        </div>
      </div>

      <div class="bg-white border border-slate-200 rounded-lg p-4">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 bg-emerald-100 rounded-lg flex items-center justify-center">
            <Shield :size="24" class="text-emerald-600" />
          </div>
          <div>
            <div class="text-sm text-slate-600">权限角色</div>
            <div class="text-2xl font-bold text-slate-900">{{ permissionStats?.total_roles || 0 }}</div>
          </div>
        </div>
      </div>

      <div class="bg-white border border-slate-200 rounded-lg p-4">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
            <CheckCircle :size="24" class="text-purple-600" />
          </div>
          <div>
            <div class="text-sm text-slate-600">已验证查询</div>
            <div class="text-2xl font-bold text-slate-900">{{ cypherStats?.total_validated || 0 }}</div>
          </div>
        </div>
      </div>

      <div class="bg-white border border-slate-200 rounded-lg p-4">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 bg-amber-100 rounded-lg flex items-center justify-center">
            <AlertCircle :size="24" class="text-amber-600" />
          </div>
          <div>
            <div class="text-sm text-slate-600">安全事件</div>
            <div class="text-2xl font-bold text-slate-900">{{ recentEvents.length }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 标签页 -->
    <el-card class="mb-4">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="租户管理" name="tenants">
          <el-alert
            type="info"
            description="💡 点击租户ID或用户ID可显示/隐藏敏感信息"
            :closable="false"
            show-icon
            class="mb-3"
          />
          <div class="space-y-4">
            <div v-for="tenant in tenants" :key="tenant.tenant_id" class="border border-slate-200 rounded-lg p-4">
              <div class="flex items-center justify-between mb-3">
                <div>
                  <div class="font-semibold text-lg">
                    {{ tenant.metadata?.company_name || tenant.tenant_id }}
                  </div>
                  <div class="text-sm text-slate-500">
                    租户ID: 
                    <span 
                      class="cursor-pointer hover:text-indigo-600" 
                      @click="toggleSensitiveInfo"
                      :title="showSensitiveInfo ? '点击隐藏' : '点击显示'"
                    >
                      {{ showSensitiveInfo ? tenant.tenant_id : '******' }}
                    </span>
                     | 用户: 
                    <span 
                      class="cursor-pointer hover:text-indigo-600"
                      @click="toggleSensitiveInfo"
                      :title="showSensitiveInfo ? '点击隐藏' : '点击显示'"
                    >
                      {{ showSensitiveInfo ? (tenant.user_id || 'N/A') : '******' }}
                    </span>
                     | 角色: {{ tenant.roles.join(', ') }}
                  </div>
                </div>
                <el-tag :type="tenant.isolation_level === 'strict' ? 'success' : 'warning'">
                  {{ tenant.isolation_level }}
                </el-tag>
              </div>

              <!-- 配额使用 -->
              <div v-if="getTenantQuota(tenant.tenant_id)" class="mt-3 space-y-2">
                <div class="flex items-center justify-between text-sm">
                  <span>查询配额</span>
                  <span>{{ formatQuotaUsage(
                    getTenantQuota(tenant.tenant_id)!.used_queries,
                    getTenantQuota(tenant.tenant_id)!.max_queries
                  ) }}</span>
                </div>
                <el-progress
                  :percentage="getQuotaPercentage(tenant.tenant_id, 'queries')"
                  :status="getQuotaStatus(
                    getTenantQuota(tenant.tenant_id)!.used_queries,
                    getTenantQuota(tenant.tenant_id)!.max_queries
                  )"
                />
                
                <div class="flex items-center justify-between text-sm">
                  <span>并发配额</span>
                  <span>{{ formatQuotaUsage(
                    getTenantQuota(tenant.tenant_id)!.used_concurrent,
                    getTenantQuota(tenant.tenant_id)!.max_concurrent
                  ) }}</span>
                </div>
                <el-progress
                  :percentage="getQuotaPercentage(tenant.tenant_id, 'concurrent')"
                  :status="getQuotaStatus(
                    getTenantQuota(tenant.tenant_id)!.used_concurrent,
                    getTenantQuota(tenant.tenant_id)!.max_concurrent
                  )"
                />
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="权限管理" name="permissions">
          <div class="space-y-4">
            <div v-for="role in roles" :key="role.name" class="border border-slate-200 rounded-lg p-4">
              <div class="flex items-center justify-between mb-2">
                <div>
                  <span class="font-semibold">{{ role.name }}</span>
                  <el-tag size="small" class="ml-2" :type="getRoleTagType(role.role_type)">
                    {{ getRoleLabel(role.role_type) }}
                  </el-tag>
                </div>
                <span v-if="role.parent_role" class="text-sm text-slate-500">
                  继承: {{ role.parent_role }}
                </span>
              </div>
              <div class="text-sm text-slate-600 mb-2">{{ role.description }}</div>
              <div class="flex flex-wrap gap-2">
                <el-tag
                  v-for="perm in role.permissions"
                  :key="perm.name"
                  size="small"
                  :type="getPermissionTagType(perm.permission_type)"
                >
                  {{ perm.permission_type }} {{ perm.resource_type }}
                </el-tag>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="Cypher 验证" name="cypher">
          <div class="space-y-4">
            <div class="bg-slate-50 rounded-lg p-4">
              <h3 class="font-semibold mb-3">Cypher 验证统计</h3>
              <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div class="text-sm text-slate-600">验证级别</div>
                  <div class="font-semibold">{{ cypherStats?.validation_level || 'normal' }}</div>
                </div>
                <div>
                  <div class="text-sm text-slate-600">最大深度</div>
                  <div class="font-semibold">{{ cypherStats?.max_depth || 5 }}</div>
                </div>
                <div>
                  <div class="text-sm text-slate-600">允许标签</div>
                  <div class="font-semibold">{{ cypherStats?.allowed_labels_count || 0 }}</div>
                </div>
                <div>
                  <div class="text-sm text-slate-600">允许关系</div>
                  <div class="font-semibold">{{ cypherStats?.allowed_rels_count || 0 }}</div>
                </div>
              </div>
            </div>

            <div>
              <h3 class="font-semibold mb-3">测试查询</h3>
              <el-alert
                type="info"
                description="⚠️ 此功能仅用于测试 Cypher 查询的安全性，不会实际执行查询"
                :closable="false"
                show-icon
                class="mb-3"
              />
              <div class="flex gap-2">
                <input
                  v-model="testQuery"
                  type="text"
                  placeholder="输入 Cypher 查询..."
                  class="flex-1 px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <button
                  @click="testCypherValidation"
                  class="px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600"
                >
                  验证
                </button>
              </div>
              
              <div v-if="validationResult" class="mt-4">
                <el-alert
                  :type="validationResult.is_valid ? 'success' : 'error'"
                  :title="validationResult.is_valid ? '查询安全' : '查询存在风险'"
                  :description="validationResult.errors.join(', ')"
                  show-icon
                />
                <div v-if="validationResult.warnings.length > 0" class="mt-2">
                  <el-alert
                    type="warning"
                    title="警告"
                    :description="validationResult.warnings.join(', ')"
                    show-icon
                  />
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="安全审计" name="audit">
          <div class="space-y-3">
            <div v-if="recentEvents.length === 0" class="text-center text-slate-500 py-8">
              暂无安全事件
            </div>
            <div
              v-for="event in recentEvents"
              :key="event.event_id"
              class="border border-slate-200 rounded-lg p-4"
            >
              <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                  <el-tag size="small" :type="getEventTypeColor(event.event_type)">
                    {{ getEventTypeLabel(event.event_type) }}
                  </el-tag>
                  <span class="text-sm text-slate-600">{{ event.tenant_id || event.user_id }}</span>
                </div>
                <span class="text-sm text-slate-500">
                  {{ new Date(event.timestamp).toLocaleString() }}
                </span>
              </div>
              <div class="text-sm text-slate-700">{{ event.details.message || JSON.stringify(event.details) }}</div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Users, Shield, CheckCircle, AlertCircle } from 'lucide-vue-next'
import {
  securityApi,
  formatQuotaUsage,
  getQuotaStatus,
  getRoleLabel,
  type TenantContext,
  type TenantStatistics,
  type TenantQuota,
  type Role,
  type PermissionStatistics,
  type CypherValidatorStats,
  type SecurityEvent,
  type ValidationResult,
  PermissionType,
  RoleType
} from '@/api/security'

const activeTab = ref('tenants')
const tenants = ref<TenantContext[]>([])
const tenantStats = ref<TenantStatistics | null>(null)
const tenantQuotas = ref<Map<string, TenantQuota>>(new Map())
const roles = ref<Role[]>([])
const permissionStats = ref<PermissionStatistics | null>(null)
const cypherStats = ref<CypherValidatorStats | null>(null)
const recentEvents = ref<SecurityEvent[]>([])
const testQuery = ref('')
const validationResult = ref<ValidationResult | null>(null)
const showSensitiveInfo = ref(false)

function toggleSensitiveInfo() {
  showSensitiveInfo.value = !showSensitiveInfo.value
}

function getTenantQuota(tenantId: string): TenantQuota | undefined {
  return tenantQuotas.value.get(tenantId)
}

function getQuotaPercentage(tenantId: string, type: string): number {
  const quota = getTenantQuota(tenantId)
  if (!quota) return 0
  const used = type === 'queries' ? quota.used_queries : quota.used_concurrent
  const max = type === 'queries' ? quota.max_queries : quota.max_concurrent
  return max > 0 ? (used / max) * 100 : 0
}

function getRoleTagType(roleType: string): 'success' | 'warning' | 'info' | 'danger' {
  const types: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    [RoleType.GUEST]: 'info',
    [RoleType.USER]: 'info',
    [RoleType.PREMIUM_USER]: 'success',
    [RoleType.OPERATOR]: 'warning',
    [RoleType.ADMIN]: 'danger',
    [RoleType.SUPER_ADMIN]: 'danger'
  }
  return types[roleType] || 'info'
}

function getPermissionTagType(permType: string): 'success' | 'warning' | 'info' | 'danger' {
  const types: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    [PermissionType.READ]: 'info',
    [PermissionType.WRITE]: 'warning',
    [PermissionType.DELETE]: 'danger',
    [PermissionType.EXECUTE]: 'success',
    [PermissionType.ADMIN]: 'danger',
    [PermissionType.SUPER_ADMIN]: 'danger'
  }
  return types[permType] || 'info'
}

function getEventTypeColor(eventType: string): 'success' | 'warning' | 'info' | 'danger' {
  const types: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    permission_denied: 'warning',
    quota_exceeded: 'danger',
    cypher_rejected: 'danger',
    tenant_access_denied: 'danger'
  }
  return types[eventType] || 'info'
}

function getEventTypeLabel(eventType: string): string {
  const labels: Record<string, string> = {
    permission_denied: '权限拒绝',
    quota_exceeded: '配额超限',
    cypher_rejected: '查询拒绝',
    tenant_access_denied: '租户访问拒绝'
  }
  return labels[eventType] || eventType
}

async function loadTenants() {
  try {
    tenants.value = await securityApi.getTenants()
    tenantStats.value = await securityApi.getTenantStatistics()
    
    // 加载每个租户的配额
    for (const tenant of tenants.value) {
      try {
        const quota = await securityApi.getTenantQuota(tenant.tenant_id)
        tenantQuotas.value.set(tenant.tenant_id, quota)
      } catch (e) {
        console.error(`Failed to load quota for ${tenant.tenant_id}`, e)
      }
    }
  } catch (error: any) {
    ElMessage.error('加载租户失败: ' + error.message)
  }
}

async function loadRoles() {
  try {
    roles.value = await securityApi.getRoles()
    permissionStats.value = await securityApi.getPermissionStatistics()
  } catch (error: any) {
    ElMessage.error('加载角色失败: ' + error.message)
  }
}

async function loadCypherStats() {
  try {
    cypherStats.value = await securityApi.getCypherValidatorStats()
  } catch (error: any) {
    ElMessage.error('加载 Cypher 统计失败: ' + error.message)
  }
}

async function testCypherValidation() {
  if (!testQuery.value.trim()) {
    ElMessage.warning('请输入查询')
    return
  }
  
  try {
    validationResult.value = await securityApi.validateCypher(testQuery.value)
  } catch (error: any) {
    ElMessage.error('验证失败: ' + error.message)
  }
}

async function loadSecurityEvents() {
  try {
    const now = new Date()
    const start = new Date(now.getTime() - 24 * 60 * 60 * 1000)
    
    recentEvents.value = await securityApi.getSecurityEvents({
      start_time: start.toISOString(),
      limit: 20
    })
  } catch (error: any) {
    console.error('加载安全事件失败', error)
  }
}

onMounted(() => {
  loadTenants()
  loadRoles()
  loadCypherStats()
  loadSecurityEvents()
})
</script>

<style scoped>
.security-monitor-panel {
  @apply p-4;
}
</style>
