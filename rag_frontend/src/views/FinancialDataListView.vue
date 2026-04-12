<template>
  <div class="financial-data-list">
    <div class="page-header">
      <h2>财务数据列表</h2>
      <div class="header-actions">
        <el-button type="primary" @click="goToEntry">
          <Plus class="icon" /> 新增数据
        </el-button>
      </div>
    </div>

    <el-card class="filter-card">
      <el-form :inline="true" :model="filterForm">
        <el-form-item label="财务年度">
          <el-select v-model="filterForm.fiscal_year" placeholder="全部年度" clearable @change="handleFilter">
            <el-option
              v-for="year in availableYears"
              :key="year"
              :label="`${year}年`"
              :value="year"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="周期类型">
          <el-select v-model="filterForm.period_type" placeholder="全部类型" clearable @change="handleFilter">
            <el-option label="年度" value="yearly" />
            <el-option label="季度" value="quarterly" />
            <el-option label="月度" value="monthly" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleFilter">
            <Search class="icon" /> 查询
          </el-button>
          <el-button @click="handleReset">
            <RefreshCw class="icon" /> 重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <el-table
        v-loading="loading"
        :data="tableData"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="fiscal_year" label="年度" width="80" align="center" />
        <el-table-column label="周期" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getPeriodTypeTag(row.period_type)">
              {{ getPeriodLabel(row.period_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="周期时间" width="180">
          <template #default="{ row }">
            {{ row.period_start }} ~ {{ row.period_end }}
          </template>
        </el-table-column>
        <el-table-column prop="total_revenue" label="总收入" width="120" align="right">
          <template #default="{ row }">
            {{ formatCurrency(row.total_revenue) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_expenses" label="总支出" width="120" align="right">
          <template #default="{ row }">
            {{ formatCurrency(row.total_expenses) }}
          </template>
        </el-table-column>
        <el-table-column label="应缴增值税" width="120" align="right">
          <template #default="{ row }">
            {{ formatCurrency(row.calculated_vat) }}
          </template>
        </el-table-column>
        <el-table-column label="企业所得税" width="120" align="right">
          <template #default="{ row }">
            {{ formatCurrency(row.calculated_corporate_tax) }}
          </template>
        </el-table-column>
        <el-table-column prop="data_status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.data_status)">
              {{ getStatusLabel(row.data_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleView(row)">
              查看
            </el-button>
            <el-button link type="primary" size="small" @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, RefreshCw } from 'lucide-vue-next'
import { financialDataApiClient, type FinancialDataResponse } from '@/api/financial-data'

const router = useRouter()

const loading = ref(false)
const tableData = ref<FinancialDataResponse[]>([])

const filterForm = reactive({
  fiscal_year: undefined as number | undefined,
  period_type: undefined as string | undefined
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const currentYear = new Date().getFullYear()
const availableYears = computed(() => {
  const years: number[] = []
  for (let y = currentYear; y >= currentYear - 5; y--) {
    years.push(y)
  }
  return years
})

async function fetchData() {
  loading.value = true
  try {
    const result = await financialDataApiClient.list({
      page: pagination.page,
      page_size: pagination.pageSize,
      fiscal_year: filterForm.fiscal_year
    })
    tableData.value = result.items
    pagination.total = result.total
  } catch (e: any) {
    console.error('Failed to fetch data:', e)
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

function handleFilter() {
  pagination.page = 1
  fetchData()
}

function handleReset() {
  filterForm.fiscal_year = undefined
  filterForm.period_type = undefined
  pagination.page = 1
  fetchData()
}

function handlePageChange() {
  fetchData()
}

function handleSizeChange() {
  pagination.page = 1
  fetchData()
}

function goToEntry() {
  router.push('/financial-data-entry')
}

function handleView(row: FinancialDataResponse) {
  router.push({
    path: '/financial-data-entry',
    query: { id: row.id, mode: 'view' }
  })
}

function handleEdit(row: FinancialDataResponse) {
  router.push({
    path: '/financial-data-entry',
    query: { id: row.id, mode: 'edit' }
  })
}

async function handleDelete(row: FinancialDataResponse) {
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${row.fiscal_year}年 ${getPeriodLabel(row.period_type)} 的财务数据吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await financialDataApiClient.delete(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e: any) {
    if (e !== 'cancel') {
      console.error('Failed to delete:', e)
      ElMessage.error('删除失败')
    }
  }
}

function getPeriodTypeTag(type: string): string {
  const map: Record<string, string> = {
    yearly: '',
    quarterly: 'success',
    monthly: 'warning'
  }
  return map[type] || ''
}

function getPeriodLabel(type: string): string {
  const map: Record<string, string> = {
    yearly: '年度',
    quarterly: '季度',
    monthly: '月度'
  }
  return map[type] || type
}

function getStatusTag(status: string): string {
  const map: Record<string, string> = {
    draft: 'info',
    confirmed: 'warning',
    final: 'success'
  }
  return map[status] || ''
}

function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    draft: '草稿',
    confirmed: '已确认',
    final: '已完成'
  }
  return map[status] || status
}

function formatCurrency(value: number): string {
  if (value == null) return '-'
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(value)
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.financial-data-list {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.icon {
  width: 16px;
  height: 16px;
  margin-right: 4px;
}

.filter-card {
  margin-bottom: 16px;
}

.table-card {
  margin-bottom: 16px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
