<template>
  <div class="debug-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>🔍 税务上传调试工具</span>
          <el-button @click="refreshPage" size="small">刷新页面</el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="环境检查" name="env">
          <el-descriptions title="当前配置" :column="1" border>
            <el-descriptions-item label="API_BASE">
              <el-tag :type="apiBaseValue ? 'success' : 'warning'">
                {{ apiBaseValue || '(空 - 使用相对路径)' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="完整上传URL">
              <code>{{ uploadUrl }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="Token状态">
              <el-tag :type="hasToken ? 'success' : 'danger'">
                {{ hasToken ? '已登录' : '未登录' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Token预览">
              <code>{{ tokenPreview }}</code>
            </el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <el-tab-pane label="直接测试" name="test">
          <el-space direction="vertical" :size="20" style="width: 100%">
            <el-card>
              <template #header>测试1: 简单ping测试</template>
              <el-button type="primary" @click="testPing" :loading="pingLoading">
                执行 ping 测试
              </el-button>
              <div v-if="pingResult" class="result-area">
                <pre>{{ JSON.stringify(pingResult, null, 2) }}</pre>
              </div>
            </el-card>

            <el-card>
              <template #header>测试2: 带认证的请求</template>
              <el-button type="primary" @click="testAuthRequest" :loading="authLoading">
                测试 /api/v1/tax-reports
              </el-button>
              <div v-if="authResult" class="result-area">
                <pre>{{ JSON.stringify(authResult, null, 2) }}</pre>
              </div>
            </el-card>

            <el-card>
              <template #header>测试3: 上传端点（模拟）</template>
              <p>使用一个小的文本文件测试上传端点是否存在</p>
              <el-button type="primary" @click="testUploadEndpoint" :loading="uploadLoading">
                测试上传端点
              </el-button>
              <div v-if="uploadResult" class="result-area">
                <pre>{{ JSON.stringify(uploadResult, null, 2) }}</pre>
              </div>
            </el-card>
          </el-space>
        </el-tab-pane>

        <el-tab-pane label="完整上传" name="full">
          <el-upload
            ref="uploadRef"
            class="upload-demo"
            drag
            :auto-upload="false"
            :limit="1"
            accept=".pdf,.xlsx,.xls,.csv,.txt"
            :on-change="handleFileChange"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              拖拽文件到此处或 <em>点击选择</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">支持 PDF、Excel、CSV 文件</div>
            </template>
          </el-upload>

          <el-button type="primary" @click="performUpload" :loading="performing" style="margin-top: 20px">
            开始上传
          </el-button>

          <el-progress
            v-if="progress !== null"
            :percentage="progress"
            :status="progress === 100 ? 'success' : undefined"
            style="margin-top: 20px"
          />

          <div v-if="fullResult" class="result-area" style="margin-top: 20px">
            <el-card>
              <template #header>上传结果</template>
              <pre>{{ JSON.stringify(fullResult, null, 2) }}</pre>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane label="浏览器Network检查" name="network">
          <el-alert type="info" :closable="false">
            <template #title>
              <strong>请按以下步骤检查浏览器开发者工具：</strong>
            </template>
            <ol style="margin: 10px 0; padding-left: 20px">
              <li>按 <kbd>F12</kbd> 打开开发者工具</li>
              <li>切换到 <strong>Network</strong> 标签</li>
              <li>执行上面的"完整上传"测试</li>
              <li>找到对应的请求，查看以下信息：
                <ul>
                  <li><strong>Name</strong>: 应该是 <code>upload</code> 或类似的</li>
                  <li><strong>Status</strong>: 应该显示具体的状态码（如 201）</li>
                  <li><strong>Type</strong>: 应该是 <code>xhr</code></li>
                  <li><strong>Size</strong>: 应该有具体的大小</li>
                </ul>
              </li>
              <li>如果状态是 <code>pending</code> 或 <code>(failed)</code>，说明请求没有到达后端</li>
            </ol>
          </el-alert>

          <el-divider />

          <el-alert type="warning" :closable="false">
            <template #title>
              <strong>常见问题：</strong>
            </template>
            <ul style="margin: 10px 0; padding-left: 20px">
              <li><strong>请求挂起</strong>: 检查后端是否启动，端口是否正确</li>
              <li><strong>404 Not Found</strong>: 检查请求URL是否正确</li>
              <li><strong>401/403</strong>: Token无效或过期</li>
              <li><strong>500</strong>: 后端内部错误，查看后端日志</li>
            </ul>
          </el-alert>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import type { UploadInstance, UploadRawFile } from 'element-plus'
import { API_BASE } from '@/config/api'

const activeTab = ref('env')
const uploadRef = ref<UploadInstance>()

const apiBaseValue = ref('')
const hasToken = ref(false)
const tokenPreview = ref('')
const selectedFile = ref<UploadRawFile | null>(null)

const pingLoading = ref(false)
const authLoading = ref(false)
const uploadLoading = ref(false)
const performing = ref(false)
const progress = ref<number | null>(null)

const pingResult = ref<any>(null)
const authResult = ref<any>(null)
const uploadResult = ref<any>(null)
const fullResult = ref<any>(null)

const uploadUrl = computed(() => {
  return `${API_BASE || ''}/api/v1/tax-reports/upload?tax_type=vat`
})

onMounted(() => {
  apiBaseValue.value = API_BASE || '(空)'
  const token = localStorage.getItem('rag_token')
  hasToken.value = !!token
  tokenPreview.value = token ? token.substring(0, 30) + '...' : '无'
})

const refreshPage = () => {
  window.location.reload()
}

const testPing = async () => {
  pingLoading.value = true
  pingResult.value = null

  try {
    console.log('🔍 测试ping，端点:', uploadUrl.value.replace('/api/v1/tax-reports/upload?tax_type=vat', '/debug/ping'))

    const response = await fetch(`${API_BASE || ''}/api/debug/ping`)
    const data = await response.json()

    pingResult.value = {
      success: true,
      status: response.status,
      data: data
    }

    ElMessage.success('Ping 测试成功')
  } catch (error: any) {
    pingResult.value = {
      success: false,
      error: error.message
    }
    ElMessage.error('Ping 测试失败: ' + error.message)
  } finally {
    pingLoading.value = false
  }
}

const testAuthRequest = async () => {
  authLoading.value = true
  authResult.value = null

  try {
    const token = localStorage.getItem('rag_token')

    console.log('🔍 测试税务列表，端点:', `${API_BASE || ''}/api/v1/tax-reports`)

    const response = await fetch(`${API_BASE || ''}/api/v1/tax-reports?page=1&page_size=10`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    const data = await response.json()

    authResult.value = {
      success: response.ok,
      status: response.status,
      data: data
    }

    if (response.ok) {
      ElMessage.success('税务列表请求成功')
    } else {
      ElMessage.warning(`请求返回: ${response.status}`)
    }
  } catch (error: any) {
    authResult.value = {
      success: false,
      error: error.message
    }
    ElMessage.error('请求失败: ' + error.message)
  } finally {
    authLoading.value = false
  }
}

const testUploadEndpoint = async () => {
  uploadLoading.value = true
  uploadResult.value = null

  try {
    const token = localStorage.getItem('rag_token')

    console.log('🔍 测试上传端点:', uploadUrl.value)

    const formData = new FormData()
    const testBlob = new Blob(['test content'], { type: 'text/plain' })
    formData.append('file', testBlob, 'test.txt')

    const response = await fetch(uploadUrl.value, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    })

    const data = await response.json().catch(() => ({}))

    uploadResult.value = {
      success: response.ok,
      status: response.status,
      data: data
    }

    if (response.ok) {
      ElMessage.success('上传端点测试成功')
    } else {
      ElMessage.warning(`上传端点返回: ${response.status}`)
    }
  } catch (error: any) {
    uploadResult.value = {
      success: false,
      error: error.message
    }
    ElMessage.error('上传端点测试失败: ' + error.message)
  } finally {
    uploadLoading.value = false
  }
}

const handleFileChange = (file: any) => {
  selectedFile.value = file.raw
  console.log('📁 已选择文件:', file.name, file.size)
}

const performUpload = () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择一个文件')
    return
  }

  performing.value = true
  progress.value = 0
  fullResult.value = null

  const token = localStorage.getItem('rag_token')

  console.log('🔍 开始完整上传测试')
  console.log('📁 文件:', selectedFile.value.name, selectedFile.value.size)
  console.log('🔗 URL:', uploadUrl.value)

  const xhr = new XMLHttpRequest()

  xhr.upload.onprogress = (event) => {
    if (event.lengthComputable) {
      progress.value = Math.round((event.loaded * 100) / event.total)
      console.log(`📤 上传进度: ${progress.value}%`)
    }
  }

  xhr.onload = () => {
    console.log('📥 请求完成，状态:', xhr.status)
    performing.value = false

    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        fullResult.value = JSON.parse(xhr.responseText)
        ElMessage.success('上传成功!')
      } catch {
        fullResult.value = { raw: xhr.responseText }
        ElMessage.success('上传成功! (响应不是JSON)')
      }
    } else {
      try {
        const errorData = JSON.parse(xhr.responseText)
        fullResult.value = { error: errorData }
        ElMessage.error(`上传失败: ${errorData.detail || xhr.status}`)
      } catch {
        fullResult.value = { error: { status: xhr.status, text: xhr.statusText } }
        ElMessage.error(`上传失败: ${xhr.status} ${xhr.statusText}`)
      }
    }
  }

  xhr.onerror = () => {
    console.error('❌ 网络错误')
    performing.value = false
    ElMessage.error('网络错误，请检查网络连接')
  }

  xhr.ontimeout = () => {
    console.error('❌ 请求超时')
    performing.value = false
    ElMessage.error('请求超时')
  }

  console.log('🚀 开始发送请求...')
  xhr.open('POST', uploadUrl.value)
  xhr.setRequestHeader('Authorization', `Bearer ${token}`)
  xhr.timeout = 120000
  xhr.send(selectedFile.value)
}
</script>

<style scoped>
.debug-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-area {
  margin-top: 15px;
}

.result-area pre {
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
  max-height: 400px;
  overflow-y: auto;
}

kbd {
  padding: 2px 6px;
  background-color: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-family: monospace;
}

code {
  background-color: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
}
</style>
