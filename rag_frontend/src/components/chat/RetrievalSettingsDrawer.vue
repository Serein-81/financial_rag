<script setup lang="ts">
import { ref, watch } from 'vue'

/**
 * 检索设置抽屉
 * 用户在聊天时切换不同的检索模式：simple / graphrag / agentic
 * 通过 chat 接口透传给后端
 */

export interface RetrievalSettings {
  retrieval_method: 'simple' | 'graphrag' | 'agentic'
  max_iterations: number
  top_k: number
  enable_rerank: boolean
  enable_graph_expansion: boolean
}

const props = defineProps<{
  modelValue: boolean
  settings: RetrievalSettings
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'save', s: RetrievalSettings): void
}>()

const local = ref<RetrievalSettings>({ ...props.settings })

watch(() => props.settings, (s) => {
  local.value = { ...s }
}, { deep: true })

watch(() => props.modelValue, (v) => {
  if (v) {
    local.value = { ...props.settings }
  }
})

function close() {
  emit('update:modelValue', false)
}

function save() {
  emit('save', { ...local.value })
}

function restoreDefault() {
  local.value = {
    retrieval_method: 'simple',
    max_iterations: 3,
    top_k: 10,
    enable_rerank: true,
    enable_graph_expansion: true,
  }
}

const methodDescriptions: Record<RetrievalSettings['retrieval_method'], string> = {
  simple: '基础向量相似度检索，速度快，适合一般查询',
  graphrag: '向量 + 知识图谱融合，准确度高，适合涉及多实体关系的查询',
  agentic: 'Agent 自主多轮检索，最智能，适合复杂的多步推理查询',
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :show-close="false"
    title="检索设置"
    direction="rtl"
    size="380px"
    @update:model-value="close"
  >
    <template #header>
      <div class="flex items-center justify-between w-full">
        <span class="text-base font-semibold">检索设置</span>
        <button @click="close" class="text-gray-400 hover:text-gray-600 p-1">✕</button>
      </div>
    </template>

    <div class="space-y-6">
      <!-- 检索方法 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">检索方法</label>
        <el-radio-group v-model="local.retrieval_method" class="w-full flex flex-col gap-2">
          <el-radio value="simple" size="large" class="!w-full !mr-0">
            <div>
              <div class="font-medium">简单向量</div>
              <div class="text-xs text-gray-500 mt-0.5">{{ methodDescriptions.simple }}</div>
            </div>
          </el-radio>
          <el-radio value="graphrag" size="large" class="!w-full !mr-0">
            <div>
              <div class="font-medium">GraphRAG</div>
              <div class="text-xs text-gray-500 mt-0.5">{{ methodDescriptions.graphrag }}</div>
            </div>
          </el-radio>
          <el-radio value="agentic" size="large" class="!w-full !mr-0">
            <div>
              <div class="font-medium">Agentic RAG</div>
              <div class="text-xs text-gray-500 mt-0.5">{{ methodDescriptions.agentic }}</div>
            </div>
          </el-radio>
        </el-radio-group>
      </div>

      <!-- 最大迭代轮数（仅 agentic 模式生效） -->
      <div v-if="local.retrieval_method === 'agentic'">
        <label class="block text-sm font-medium text-gray-700 mb-2">
          最大迭代轮数
          <span class="text-xs text-gray-400 ml-1">(仅 Agentic 模式)</span>
        </label>
        <div class="px-2">
          <el-slider
            v-model="local.max_iterations"
            :min="1"
            :max="5"
            :step="1"
            show-stops
            :marks="{ 1: '1', 2: '2', 3: '3', 4: '4', 5: '5' }"
          />
        </div>
      </div>

      <!-- Top K -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">
          返回文档数 (Top K)
        </label>
        <el-input-number
          v-model="local.top_k"
          :min="1"
          :max="50"
          :step="1"
          class="w-full"
        />
      </div>

      <!-- 启用重排序 -->
      <div class="flex items-center justify-between">
        <div>
          <div class="text-sm font-medium text-gray-700">启用重排序 (Rerank)</div>
          <div class="text-xs text-gray-500 mt-0.5">对初步结果进行精排，提高准确度</div>
        </div>
        <el-switch v-model="local.enable_rerank" />
      </div>

      <!-- 启用图谱扩展 -->
      <div class="flex items-center justify-between">
        <div>
          <div class="text-sm font-medium text-gray-700">启用知识图谱扩展</div>
          <div class="text-xs text-gray-500 mt-0.5">从检索结果出发扩展相关实体</div>
        </div>
        <el-switch v-model="local.enable_graph_expansion" />
      </div>

      <!-- 提示信息 -->
      <div class="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-700">
        💡 配置会保存到本地，下次聊天自动应用
      </div>
    </div>

    <template #footer>
      <div class="flex items-center justify-between w-full">
        <el-button text @click="restoreDefault">恢复默认</el-button>
        <div class="flex gap-2">
          <el-button @click="close">取消</el-button>
          <el-button type="primary" @click="save">保存</el-button>
        </div>
      </div>
    </template>
  </el-drawer>
</template>
