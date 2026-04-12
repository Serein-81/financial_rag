<template>
  <div class="diagnostic-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>税务上传诊断工具</span>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="诊断检查" name="diagnostic">
          <div class="diagnostic-section">
            <h3>1. 环境变量检查</h3>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="API_BASE">
                <el-tag :type="apiBase ? 'success' : 'danger'">
                  {{ apiBase || '未设置' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="Token 状态">
                <el-tag :type="hasToken ? 'success' : 'danger'">
                  {{ hasToken ? '已登录' : '未登录' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="Token 前20字符">
                <code>{{ tokenPreview }}</code>
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <el-divider />

          <div class="diagnostic-section">
            <h3>2. 网络请求测试</h3>
            <el-space wrap>
              <el-button type="primary" @click="testPing" :loading="pingLoading">
                测试 /debug/ping
              </el-button>
              <el-button type="primary" @click="testDiagnostic" :loading="diagnosticLoading">
                测试 /debug/tax-upload-diagnostic
              </el-button>
              <el-button type="primary" @click="testDirectUpload" :loading="directLoading">
                测试直接上传（不带认证）
              </el-button>
            </el-space>

            <div v-if="testResults.length > 0" class="test-results">
              <h4>测试结果：</h4>
              <el-card v-for="(result, index) in testResults" :key="index" class="result-card">
                <template #header>
                  <span>{{ result.title }}</span>
                  <el-tag :type="result.success ? 'success' : 'danger'" size="small">
                    {{ result.success ? '成功' : '失败' }}
                  </el-tag>
                </template>
                <pre>{{ JSON.stringify(result.data, null, 2) }}</pre>
                <div v-if="result.error" class="error-message">
                  错误: {{ result.error }}
                </div>
              </el-card>
            </div>
          </div>

          <el-divider />

          <div class="diagnostic-section">
            <h3>3. 完整上传测试</h3>
            <el-upload
              ref="uploadRef"
              class="upload-demo"
              drag
              :auto-upload="false"
              :limit="1"
              accept=".pdf,.xlsx,.xls,.csv"
              :on-change="handleFileChange"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                拖拽文件到此处或 <em>点击选择</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">支持 PDF、Excel、CSV 文件，最大 50MB</div>
              </template>
            </el-upload>

            <div class="upload-actions">
              <el-button type="primary" @click="testUploadWithProgress" :loading="uploadLoading">
                测试上传（带进度）
              </el-button>
              <el-button @click="clearResults">清除结果</el-button>
            </div>

            <div v-if="uploadProgress !== null" class="upload-progress">
              <el-progress :percentage="uploadProgress" :status="uploadProgress === 100 ? 'success' : undefined" />
            </div>

            <div v-if="uploadResult" class="upload-result">
              <el-card>
                <template #header>
                  <span>上传结果</span>
                </template>
                <pre>{{ JSON.stringify(uploadResult, null, 2) }}</pre>
              </el-card>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="问题排查指南" name="guide">
          <div class="guide-content">
            <h3>常见问题及解决方案</h3>

            <el-collapse v-model="activeCollapse">
              <el-collapse-item title="问题1: 请求一直挂起" name="problem1">
                <div class="collapse-content">
                  <h4>可能原因：</h4>
                  <ul>
                    <li><strong>后端服务未启动</strong> - 请检查后端是否在 8000 端口运行</li>
                    <li><strong>网络代理配置错误</strong> - 检查 vite.config.ts 中的 proxy 配置</li>
                    <li><strong>CORS 问题</strong> - 浏览器阻止了跨域请求</li>
                  </ul>

                  <h4>排查步骤：</h4>
                  <ol>
                    <li>打开浏览器开发者工具 (F12)</li>
                    <li>切换到 Network 面板</li>
                    <li>查看请求的 URL，确认是否正确</li>
                    <li>查看是否有红色或黄色警告</li>
                    <li>检查 Console 控制台是否有错误信息</li>
                  </ol>
                </div>
              </el-collapse-item>

              <el-collapse-item title="问题2: 401/403 认证错误" name="problem2">
                <div class="collapse-content">
                  <h4>可能原因：</h4>
                  <ul>
                    <li><strong>Token 过期</strong> - 需要重新登录</li>
                    <li><strong>Token 未正确传递</strong> - 请求头中缺少 Authorization</li>
                    <li><strong>Token 格式错误</strong> - Bearer token 格式不正确</li>
                  </ul>

                  <h4>排查步骤：</h4>
                  <ol>
                    <li>点击上方"诊断检查"标签</li>
                    <li>查看 Token 状态是否为"已登录"</li>
                    <li>在 Network 面板中查看请求头</li>
                  </ol>
                </div>
              </el-collapse-item>

              <el-collapse-item title="问题3: 后端无日志输出" name="problem3">
                <div class="collapse-content">
                  <h4>可能原因：</h4>
                  <ul>
                    <li><strong>请求未到达后端</strong> - 前端代理配置问题</li>
                    <li><strong>限流中间件拦截</strong> - 请求被限流</li>
                    <li><strong>租户中间件拦截</strong> - 缺少 tenant_id</li>
                  </ul>

                  <h4>排查步骤：</h4>
                  <ol>
                    <li>使用诊断端点测试请求是否到达</li>
                    <li>检查后端控制台是否有任何输出</li>
                    <li>查看日志文件 logs/app.log</li>
                  </ol>
                </div>
              </el-collapse-item>

              <el-collapse-item title="问题4: 30秒超时" name="problem4">
                <div class="collapse-content">
                  <h4>可能原因：</h4>
                  <ul>
                    <li><strong>请求被卡在代理层</strong> - Vite 代理未正确转发</li>
                    <li><strong>后端处理超时</strong> - 某些操作耗时过长</li>
                    <li><strong>网络连接问题</strong> - 网络不稳定</li>
                  </ul>

                  <h4>排查步骤：</h4>
                  <ol>
                    <li>检查 vite.config.ts 的 proxy 配置</li>
                    <li>尝试直接访问后端 API</li>
                    <li>检查浏览器 Network 面板的 Timing 信息</li>
                  </ol>
                </div>
              </el-collapse-item>
            </el-collapse>

            <div class="network-guide">
              <h3>浏览器 Network 面板使用指南</h3>
              <el-steps direction="vertical" :space="100" :active="4">
                <el-step title="打开开发者工具" description="按 F12 或右键 -> 检查" />
                <el-step title="切换到 Network 面板" description="点击 Network 标签" />
                <el-step title="复现问题" description="执行上传操作" />
                <el-step title="查看请求详情" description="点击挂起的请求" />
                <el-step title="检查 General 部分" description="查看 Request URL 是否正确" />
                <el-step title="检查 Headers 部分" description="确认 Authorization header 是否存在" />
                <el-step title="检查 Timing 部分" description="查看请求耗时" />
              </el-steps>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import type { UploadInstance, UploadRawFile } from 'element-plus'
import { API_BASE } from '@/config/api'

const activeTab = ref('diagnostic')
const activeCollapse = ref('problem1')

const apiBase = ref(API_BASE)
const token = ref(localStorage.getItem('rag_token') || '')
const hasToken = computed(() => !!token.value)
const tokenPreview = computed(() => token.value ? token.value.substring(0, 20) + '...' : '无')

const uploadRef = ref<UploadInstance>()
const selectedFile = ref<UploadRawFile | null>(null)

const pingLoading = ref(false)
const diagnosticLoading = ref(false)
const directLoading = ref(false)
const uploadLoading = ref(false)

const testResults = ref<Array<{
  title: string
  success: boolean
  data: any
  error?: string
}>>([])

const uploadProgress = ref<number | null>(null)
const uploadResult = ref<any>(null)

const handleFileChange = (file: any) => {
  selectedFile.value = file.raw
}

const testPing = async () => {
  pingLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/debug/ping`)
    const data = await response.json()
    testResults.value.push({
      title: 'Ping 测试',
      success: true,
      data
    })
    ElMessage.success('Ping 测试成功')
  } catch (error: any) {
    testResults.value.push({
      title: 'Ping 测试',
      success: false,
      data: null,
      error: error.message
    })
    ElMessage.error('Ping 测试失败: ' + error.message)
  } finally {
    pingLoading.value = false
  }
}

const testDiagnostic = async () => {
  diagnosticLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/debug/tax-upload-diagnostic`, {
      headers: {
        'Authorization': `Bearer ${token.value}`
      }
    })
    const data = await response.json()
    testResults.value.push({
      title: '诊断端点测试',
      success: response.ok,
      data
    })
    if (response.ok) {
      ElMessage.success('诊断端点测试成功')
    } else {
      ElMessage.warning('诊断端点返回错误')
    }
  } catch (error: any) {
    testResults.value.push({
      title: '诊断端点测试',
      success: false,
      data: null,
      error: error.message
    })
    ElMessage.error('诊断端点测试失败: ' + error.message)
  } finally {
    diagnosticLoading.value = false
  }
}

const testDirectUpload = async () => {
  directLoading.value = true
  try {
    const formData = new FormData()
    const testContent = new Blob(['Test content'], { type: 'text/plain' })
    formData.append('file', testContent, 'test.txt')

    const response = await fetch(`${API_BASE}/api/v1/tax-reports/upload?tax_type=VAT`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token.value}`
      },
      body: formData
    })

    const data = await response.json().catch(() => ({}))

    testResults.value.push({
      title: '直接上传测试（不带真实文件）',
      success: response.ok,
      data: {
        status: response.status,
        statusText: response.statusText,
        body: data
      }
    })

    if (response.ok) {
      ElMessage.success('直接上传测试成功')
    } else {
      ElMessage.warning(`直接上传测试返回: ${response.status} ${response.statusText}`)
    }
  } catch (error: any) {
    testResults.value.push({
      title: '直接上传测试',
      success: false,
      data: null,
      error: error.message
    })
    ElMessage.error('直接上传测试失败: ' + error.message)
  } finally {
    directLoading.value = false
  }
}

const testUploadWithProgress = () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择一个文件')
    return
  }

  uploadLoading.value = true
  uploadProgress.value = 0
  uploadResult.value = null

  const xhr = new XMLHttpRequest()
  const formData = new FormData()
  formData.append('file', selectedFile.value)

  xhr.upload.onprogress = (event) => {
    if (event.lengthComputable) {
      uploadProgress.value = Math.round((event.loaded * 100) / event.total)
    }
  }

  xhr.onload = () => {
    uploadLoading.value = false
    uploadProgress.value = 100

    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        uploadResult.value = JSON.parse(xhr.responseText)
        ElMessage.success('上传测试成功')
      } catch {
        uploadResult.value = { raw: xhr.responseText }
        ElMessage.success('上传测试成功（响应不是 JSON）')
      }
    } else {
      try {
        uploadResult.value = JSON.parse(xhr.responseText)
        ElMessage.error(`上传测试失败: ${xhr.status} - ${uploadResult.value.detail || xhr.statusText}`)
      } catch {
        uploadResult.value = { raw: xhr.responseText }
        ElMessage.error(`上传测试失败: ${xhr.status} - ${xhr.statusText}`)
      }
    }
  }

  xhr.onerror = () => {
    uploadLoading.value = false
    ElMessage.error('网络错误')
  }

  xhr.ontimeout = () => {
    uploadLoading.value = false
    ElMessage.error('请求超时')
  }

  xhr.open('POST', `${API_BASE}/api/v1/tax-reports/upload?tax_type=VAT`)
  xhr.setRequestHeader('Authorization', `Bearer ${token.value}`)
  xhr.timeout = 120000
  xhr.send(formData)
}

const clearResults = () => {
  testResults.value = []
  uploadProgress.value = null
  uploadResult.value = null
}
</script>

<style scoped>
.diagnostic-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  font-size: 18px;
  font-weight: bold;
}

.diagnostic-section {
  margin-bottom: 20px;
}

.diagnostic-section h3 {
  margin-bottom: 15px;
  color: #409eff;
}

.test-results {
  margin-top: 20px;
}

.result-card {
  margin-bottom: 15px;
}

.result-card pre {
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
}

.error-message {
  color: #f56c6c;
  margin-top: 10px;
  padding: 10px;
  background-color: #fef0f0;
  border-radius: 4px;
}

.upload-actions {
  margin-top: 20px;
}

.upload-progress {
  margin-top: 20px;
}

.upload-result {
  margin-top: 20px;
}

.upload-result pre {
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}

.guide-content h3 {
  margin-bottom: 20px;
  color: #409eff;
}

.collapse-content h4 {
  margin: 10px 0;
  color: #606266;
}

.collapse-content ul,
.collapse-content ol {
  margin: 10px 0;
  padding-left: 20px;
}

.collapse-content li {
  margin: 5px 0;
}

.network-guide {
  margin-top: 30px;
  padding: 20px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.network-guide h3 {
  margin-bottom: 20px;
}
</style>
