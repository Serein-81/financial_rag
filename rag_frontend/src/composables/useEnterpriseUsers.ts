/**
 * 企业用户数据 Hook
 */

import { ref, onMounted } from 'vue'
import { enterpriseApi, type EnterpriseUser } from '@/api/enterprise'
import { ElMessage } from 'element-plus'

export const useEnterpriseUsers = () => {
  const users = ref<EnterpriseUser[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const fetchUsers = async () => {
    loading.value = true
    error.value = null

    try {
      users.value = await enterpriseApi.getTenantUsers()
    } catch (err) {
      error.value = err instanceof Error ? err.message : '获取用户失败'
      ElMessage.error('获取用户列表失败')
      console.error('Failed to fetch enterprise users:', err)
    } finally {
      loading.value = false
    }
  }

  const getRecentUsers = (count: number = 5) => {
    return users.value
      .slice()
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, count)
  }

  const getActiveUsers = () => {
    return users.value.filter(user => user.is_active)
  }

  const getAdminUsers = () => {
    return users.value.filter(user => user.is_admin)
  }

  onMounted(() => {
    fetchUsers()
  })

  return {
    users,
    loading,
    error,
    fetchUsers,
    getRecentUsers,
    getActiveUsers,
    getAdminUsers
  }
}
