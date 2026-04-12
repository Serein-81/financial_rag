<script setup lang="ts">
import { ref, computed } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { Search, Database, FileText, Sparkles, Loader2, Globe, Monitor, ToggleLeft, ToggleRight, X, ExternalLink, AlertCircle, CheckCircle, Info, ChevronDown, ChevronUp, Sliders, Cpu, BookOpen, Type } from 'lucide-vue-next'
import { request } from '@/utils/request'
import { searchApi, type SearchResult, type WebSearchResult } from '@/api/search'
import { marked } from 'marked'

const knowledgeStore = useKnowledgeStore()

marked.setOptions({
  breaks: true,
  gfm: true
})

function renderMarkdown(content: string): string {
  if (!content) return ''
  return marked.parse(content, { async: false }) as string
}

const searchQuery = ref('')
const localResults = ref<SearchResult[]>([])
const webResults = ref<WebSearchResult[]>([])
const isSearching = ref(false)
const searchTime = ref(0)
const enableWebSearch = ref(false)
const enableSynonymSearch = ref(true)
const showAdvancedSettings = ref(false)
const searchError = ref('')
const webSearchAvailable = ref(true)

// 权重设置
const vectorWeight = ref(0.5)
const synonymWeight = ref(0.3)
const fulltextWeight = ref(0.2)

// 搜索模式
const searchMode = ref<'basic' | 'web' | 'synonym'>('basic')

// 详情弹窗
const showDetailModal = ref(false)
const selectedResult = ref<SearchResult | WebSearchResult | null>(null)
const selectedResultType = ref<'local' | 'web'>('local')

const selectedKB = computed(() => knowledgeStore.selectedKnowledgeBase)

const hasResults = computed(() => {
  if (enableWebSearch.value && !enableSynonymSearch.value) {
    return localResults.value.length > 0 || webResults.value.length > 0
  } else if (enableSynonymSearch.value && !enableWebSearch.value) {
    return localResults.value.length > 0
  } else if (enableWebSearch.value && enableSynonymSearch.value) {
    return localResults.value.length > 0 || webResults.value.length > 0
  }
  return localResults.value.length > 0
})

// 过滤相似度低于50%的结果
const filteredLocalResults = computed(() => {
  return localResults.value.filter(r => r.score >= 0.5)
})

const filteredWebResults = computed(() => {
  return webResults.value.filter(r => r.score >= 0.5)
})

const filteredHasResults = computed(() => {
  if (enableWebSearch.value && !enableSynonymSearch.value) {
    return filteredLocalResults.value.length > 0 || filteredWebResults.value.length > 0
  } else if (enableSynonymSearch.value && !enableWebSearch.value) {
    return filteredLocalResults.value.length > 0
  } else if (enableWebSearch.value && enableSynonymSearch.value) {
    return filteredLocalResults.value.length > 0 || filteredWebResults.value.length > 0
  }
  return filteredLocalResults.value.length > 0
})

// 搜索模式标签
const currentSearchModeLabel = computed(() => {
  if (enableWebSearch.value && enableSynonymSearch.value) return '联网 + 同义词'
  if (enableWebSearch.value) return '联网搜索'
  if (enableSynonymSearch.value) return '同义词搜索'
  return '基础搜索'
})

async function handleSearch() {
  if (!searchQuery.value.trim() || isSearching.value) return

  isSearching.value = true
  localResults.value = []
  webResults.value = []
  searchError.value = ''
  webSearchAvailable.value = true

  try {
    const startTime = Date.now()

    // 场景1: 联网 + 同义词（最强模式）
    if (enableWebSearch.value && enableSynonymSearch.value) {
      try {
        // 先进行同义词搜索
        const synonymResponse = await searchApi.hybridSearchWithSynonym({
          query: searchQuery.value,
          top_k: 10,
          kb_id: selectedKB.value?.id || null,
          enable_synonym: true,
          enable_fulltext: true,
          vector_weight: vectorWeight.value,
          synonym_weight: synonymWeight.value,
          fulltext_weight: fulltextWeight.value,
          score_threshold: 0.3
        })

        // 同时获取联网结果
        const [localData, webData] = await Promise.all([
          Promise.resolve(synonymResponse),
          searchApi.hybridSearch({
            query: searchQuery.value,
            top_k: 10,
            kb_id: selectedKB.value?.id || null,
            enable_web: true
          }).catch(() => ({ kb_results: [], web_results: [], web_available: false }))
        ])

        searchTime.value = Date.now() - startTime
        localResults.value = localData.results || []
        webResults.value = webData.web_results || []
        webSearchAvailable.value = webData.web_available

        if (!webData.web_available) {
          searchError.value = '联网搜索服务暂不可用，已返回本地知识库结果'
        }
      } catch (error: any) {
        searchTime.value = Date.now() - startTime
        console.error('Combined search failed:', error)
        searchError.value = '搜索失败，请重试'
      }
    }
    // 场景2: 仅同义词搜索
    else if (enableSynonymSearch.value && !enableWebSearch.value) {
      try {
        const response = await searchApi.hybridSearchWithSynonym({
          query: searchQuery.value,
          top_k: 10,
          kb_id: selectedKB.value?.id || null,
          enable_synonym: true,
          enable_fulltext: true,
          vector_weight: vectorWeight.value,
          synonym_weight: synonymWeight.value,
          fulltext_weight: fulltextWeight.value,
          score_threshold: 0.3
        })

        searchTime.value = Date.now() - startTime
        localResults.value = response.results || []
      } catch (error: any) {
        searchTime.value = Date.now() - startTime
        console.error('Synonym search failed:', error)
        searchError.value = '同义词搜索失败，已切换到基础搜索'

        const response = await request<{ results: SearchResult[], total_time: number }>('/search/query', {
          method: 'POST',
          data: JSON.stringify({
            query: searchQuery.value,
            top_k: 10,
            kb_id: selectedKB.value?.id ?? null
          })
        })

        localResults.value = response.results || []
      }
    }
    // 场景3: 仅联网搜索（原有逻辑）
    else if (enableWebSearch.value && !enableSynonymSearch.value) {
      try {
        const response = await searchApi.hybridSearch({
          query: searchQuery.value,
          top_k: 10,
          kb_id: selectedKB.value?.id ?? null,
          enable_web: true
        })

        searchTime.value = Date.now() - startTime
        localResults.value = response.kb_results || []
        webResults.value = response.web_results || []
        webSearchAvailable.value = response.web_available

        if (!response.web_available) {
          searchError.value = '联网搜索服务暂不可用，已返回本地知识库结果'
        }
      } catch (error: any) {
        searchTime.value = Date.now() - startTime
        console.error('Hybrid search failed, falling back to local search:', error)
        searchError.value = '联网搜索失败，已切换到本地知识库搜索'

        const response = await request<{ results: SearchResult[], total_time: number }>('/search/query', {
          method: 'POST',
          data: JSON.stringify({
            query: searchQuery.value,
            top_k: 10,
            kb_id: selectedKB.value?.id ?? null
          })
        })

        localResults.value = response.results || []
      }
    }
    // 场景4: 基础搜索
    else {
      const response = await request<{ results: SearchResult[], total_time: number }>('/search/query', {
        method: 'POST',
        data: JSON.stringify({
          query: searchQuery.value,
          top_k: 10,
          kb_id: selectedKB.value?.id ?? null
        })
      })

      searchTime.value = Date.now() - startTime
      localResults.value = response.results || []
    }
  } catch (error) {
    console.error('Search error:', error)
    searchError.value = '搜索过程中出现错误，请重试'
  } finally {
    isSearching.value = false
  }
}

function openDetail(result: SearchResult | WebSearchResult, type: 'local' | 'web') {
  selectedResult.value = result
  selectedResultType.value = type
  showDetailModal.value = true
}

function closeDetail() {
  showDetailModal.value = false
  selectedResult.value = null
}

function getResultIcon(type: 'local' | 'web') {
  return type === 'local' ? FileText : Globe
}

function getResultColor(type: 'local' | 'web') {
  return type === 'local'
    ? 'from-emerald-500 to-teal-600'
    : 'from-teal-500 to-emerald-600'
}
</script>

<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-slate-100 via-emerald-50/30 to-teal-50/30 h-full">
    <!-- Top Bar -->
    <div class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center">
          <Search :size="20" class="text-white" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-gray-900">语义搜索</h2>
          <p class="text-xs text-gray-500">在知识库中搜索相关内容</p>
        </div>
      </div>

      <!-- KB Selector -->
      <div class="flex items-center gap-2 px-4 py-2 bg-gray-50 rounded-xl border border-gray-200">
        <Database :size="16" class="text-gray-500" />
        <select
          v-model="knowledgeStore.selectedKnowledgeBaseId"
          class="bg-transparent text-sm text-gray-700 outline-none cursor-pointer"
        >
          <option :value="null">所有知识库</option>
          <option v-for="kb in knowledgeStore.knowledgeBases" :key="kb.id" :value="kb.id">
            {{ kb.name }}
          </option>
        </select>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 overflow-y-auto p-8">
      <div class="max-w-6xl mx-auto space-y-8">
        <!-- Search Box -->
        <div class="bg-white rounded-2xl shadow-xl p-8">
          <div class="flex gap-3 mb-4">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="输入你想搜索的内容..."
              class="flex-1 px-5 py-4 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 focus:bg-white focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all outline-none text-lg"
              @keydown.enter="handleSearch"
            />
            <button
              @click="handleSearch"
              :disabled="isSearching || !searchQuery.trim()"
              class="px-8 py-4 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl flex items-center gap-3 font-medium"
            >
              <Search :size="20" v-if="!isSearching" />
              <Loader2 :size="20" class="animate-spin" v-else />
              <span>{{ isSearching ? '搜索中...' : '搜索' }}</span>
            </button>
          </div>

          <!-- Search Options -->
          <div class="mt-4 space-y-3">
            <!-- Primary Search Toggles -->
            <div class="flex items-center gap-3">
              <!-- Web Search Toggle -->
              <div
                @click="enableWebSearch = !enableWebSearch"
                class="flex-1 flex items-center gap-3 px-4 py-3 rounded-xl border-2 cursor-pointer transition-all"
                :class="enableWebSearch
                  ? 'bg-gradient-to-r from-emerald-50 to-teal-50 border-emerald-300 shadow-sm'
                  : 'bg-gray-50 border-gray-200 hover:border-gray-300'"
              >
                <div :class="enableWebSearch ? 'bg-emerald-500' : 'bg-gray-400'" class="w-10 h-10 rounded-lg flex items-center justify-center shadow-sm transition-colors">
                  <Globe :size="20" class="text-white" />
                </div>
                <div class="flex-1">
                  <div class="font-medium" :class="enableWebSearch ? 'text-emerald-900' : 'text-gray-700'">联网搜索</div>
                  <div class="text-xs" :class="enableWebSearch ? 'text-emerald-600' : 'text-gray-500'">实时获取互联网信息</div>
                </div>
                <div :class="enableWebSearch ? 'bg-emerald-500' : 'bg-gray-300'" class="w-12 h-6 rounded-full p-1 transition-colors">
                  <div
                    class="w-4 h-4 bg-white rounded-full shadow-sm transition-transform"
                    :class="enableWebSearch ? 'translate-x-6' : 'translate-x-0'"
                  ></div>
                </div>
              </div>

              <!-- Synonym Search Toggle -->
              <div
                @click="enableSynonymSearch = !enableSynonymSearch"
                class="flex-1 flex items-center gap-3 px-4 py-3 rounded-xl border-2 cursor-pointer transition-all"
                :class="enableSynonymSearch
                  ? 'bg-gradient-to-r from-emerald-50 to-green-50 border-emerald-300 shadow-sm'
                  : 'bg-gray-50 border-gray-200 hover:border-gray-300'"
              >
                <div :class="enableSynonymSearch ? 'bg-emerald-500' : 'bg-gray-400'" class="w-10 h-10 rounded-lg flex items-center justify-center shadow-sm transition-colors">
                  <Sparkles :size="20" class="text-white" />
                </div>
                <div class="flex-1">
                  <div class="font-medium" :class="enableSynonymSearch ? 'text-emerald-900' : 'text-gray-700'">同义词扩展</div>
                  <div class="text-xs" :class="enableSynonymSearch ? 'text-emerald-600' : 'text-gray-500'">智能匹配相关词汇</div>
                </div>
                <div :class="enableSynonymSearch ? 'bg-emerald-500' : 'bg-gray-300'" class="w-12 h-6 rounded-full p-1 transition-colors">
                  <div
                    class="w-4 h-4 bg-white rounded-full shadow-sm transition-transform"
                    :class="enableSynonymSearch ? 'translate-x-6' : 'translate-x-0'"
                  ></div>
                </div>
              </div>
            </div>

            <!-- Advanced Settings Toggle -->
            <div
              v-if="enableSynonymSearch"
              @click="showAdvancedSettings = !showAdvancedSettings"
              class="flex items-center justify-between px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg cursor-pointer transition-colors"
            >
              <div class="flex items-center gap-2 text-sm text-gray-600">
                <Sliders :size="16" />
                <span>高级设置</span>
              </div>
              <component :is="showAdvancedSettings ? ChevronUp : ChevronDown" :size="16" class="text-gray-500" />
            </div>

            <!-- Advanced Settings Panel -->
            <div
              v-if="showAdvancedSettings && enableSynonymSearch"
              class="p-4 bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl border border-gray-200 space-y-4"
            >
              <div class="text-sm font-medium text-gray-700 mb-3">搜索权重配置</div>

              <!-- Vector Weight -->
              <div class="space-y-2">
                <div class="flex items-center justify-between text-sm">
                  <div class="flex items-center gap-2">
                    <Cpu :size="14" class="text-emerald-600" />
                    <span class="text-gray-600">向量搜索权重</span>
                  </div>
                  <span class="font-medium text-emerald-600">{{ (vectorWeight * 100).toFixed(0) }}%</span>
                </div>
                <input
                  type="range"
                  v-model.number="vectorWeight"
                  min="0"
                  max="1"
                  step="0.1"
                  class="w-full h-2 bg-emerald-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
                />
                <div class="flex justify-between text-xs text-gray-400">
                  <span>注重语义理解</span>
                  <span>注重精确匹配</span>
                </div>
              </div>

              <!-- Synonym Weight -->
              <div class="space-y-2">
                <div class="flex items-center justify-between text-sm">
                  <div class="flex items-center gap-2">
                    <BookOpen :size="14" class="text-emerald-600" />
                    <span class="text-gray-600">同义词权重</span>
                  </div>
                  <span class="font-medium text-emerald-600">{{ (synonymWeight * 100).toFixed(0) }}%</span>
                </div>
                <input
                  type="range"
                  v-model.number="synonymWeight"
                  min="0"
                  max="1"
                  step="0.1"
                  class="w-full h-2 bg-emerald-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
                />
                <div class="flex justify-between text-xs text-gray-400">
                  <span>注重原词匹配</span>
                  <span>注重同义词扩展</span>
                </div>
              </div>

              <!-- Fulltext Weight -->
              <div class="space-y-2">
                <div class="flex items-center justify-between text-sm">
                  <div class="flex items-center gap-2">
                    <Type :size="14" class="text-emerald-600" />
                    <span class="text-gray-600">全文搜索权重</span>
                  </div>
                  <span class="font-medium text-emerald-600">{{ (fulltextWeight * 100).toFixed(0) }}%</span>
                </div>
                <input
                  type="range"
                  v-model.number="fulltextWeight"
                  min="0"
                  max="1"
                  step="0.1"
                  class="w-full h-2 bg-emerald-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
                />
                <div class="flex justify-between text-xs text-gray-400">
                  <span>注重模糊匹配</span>
                  <span>注重精确短语</span>
                </div>
              </div>

              <!-- Weight Summary -->
              <div class="pt-2 border-t border-gray-200">
                <div class="text-xs text-gray-500 text-center">
                  当前权重配置：向量 {{ (vectorWeight * 100).toFixed(0) }}% · 同义词 {{ (synonymWeight * 100).toFixed(0) }}% · 全文 {{ (fulltextWeight * 100).toFixed(0) }}%
                </div>
              </div>
            </div>
          </div>

          <!-- Error/Info Messages -->
          <div v-if="searchError" class="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-3">
            <AlertCircle :size="20" class="text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <p class="text-sm text-amber-800">{{ searchError }}</p>
            </div>
          </div>

          <!-- Search Stats -->
          <div v-if="filteredHasResults" class="mt-4 flex items-center gap-4 flex-wrap">
            <div class="flex items-center gap-2 text-sm text-gray-600">
              <span class="px-2 py-1 bg-gradient-to-r from-emerald-100 to-teal-100 text-emerald-700 rounded-lg font-medium">
                {{ currentSearchModeLabel }}
              </span>
            </div>
            <template v-if="enableWebSearch">
              <div class="flex items-center gap-2 text-sm">
                <Monitor :size="14" class="text-emerald-600" />
                <span class="text-gray-700">本地知识库</span>
                <span class="font-semibold text-emerald-600">{{ filteredLocalResults.length }}</span>
                <span class="text-gray-400">个结果</span>
              </div>
              <div class="flex items-center gap-2 text-sm">
                <Globe :size="14" class="text-emerald-600" />
                <span class="text-gray-700">联网搜索</span>
                <span class="font-semibold text-emerald-600">{{ filteredWebResults.length }}</span>
                <span class="text-gray-400">个结果</span>
              </div>
            </template>
            <template v-else>
              <div class="flex items-center gap-2 text-sm">
                <Monitor :size="14" class="text-emerald-600" />
                <span class="text-gray-700">本地知识库</span>
                <span class="font-semibold text-emerald-600">{{ filteredLocalResults.length }}</span>
                <span class="text-gray-400">个结果</span>
              </div>
            </template>
            <div class="flex items-center gap-2 text-sm text-gray-500">
              <span>耗时</span>
              <span class="font-semibold text-gray-700">{{ searchTime }}ms</span>
            </div>
            <div class="text-xs text-gray-400">
              (仅显示相似度 ≥50% 的结果)
            </div>
          </div>
        </div>

        <!-- Single Column Results (Local Only) -->
        <div v-if="(!enableWebSearch || (enableWebSearch && !filteredWebResults.length && filteredLocalResults.length > 0)) && filteredLocalResults.length > 0" class="space-y-4">
          <div class="flex items-center justify-between mb-4 p-4 bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl border border-emerald-200">
            <div class="flex items-center gap-2">
              <Monitor :size="20" class="text-emerald-600" />
              <h3 class="text-lg font-semibold text-gray-900">本地知识库结果</h3>
              <span class="px-2 py-1 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium">
                {{ filteredLocalResults.length }} 个结果
              </span>
            </div>
            <div v-if="enableSynonymSearch" class="flex items-center gap-2">
              <Sparkles :size="14" class="text-emerald-600" />
              <span class="text-xs text-emerald-600 font-medium">同义词搜索模式</span>
            </div>
          </div>

          <div
            v-for="(result, index) in filteredLocalResults"
            :key="index"
            @click="openDetail(result, 'local')"
            class="bg-white rounded-2xl shadow-md hover:shadow-lg transition-all p-6 border border-gray-200 cursor-pointer hover:border-emerald-300 hover:bg-emerald-50/30"
          >
            <div class="flex items-start gap-4">
              <div class="w-12 h-12 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md">
                <FileText :size="24" class="text-white" />
              </div>

              <div class="flex-1">
                <div class="flex items-center justify-between mb-3">
                  <div class="flex items-center gap-2">
                    <h3 class="font-semibold text-gray-900">{{ result.source_file }}</h3>
                    <span v-if="enableSynonymSearch" class="px-2 py-0.5 bg-emerald-50 text-emerald-600 rounded text-xs">
                      ✨ 同义词
                    </span>
                  </div>
                  <div class="flex items-center gap-2">
                    <div class="flex items-center gap-2 px-3 py-1 bg-emerald-50 rounded-lg">
                      <Sparkles :size="14" class="text-emerald-600" />
                      <span class="text-sm font-medium text-emerald-700">
                        {{ (result.score * 100).toFixed(1) }}%
                      </span>
                    </div>
                    <ExternalLink :size="16" class="text-gray-400" />
                  </div>
                </div>

                <p class="text-gray-700 leading-relaxed line-clamp-3 break-words">{{ result.content }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Dual Column Results (Local + Web) -->
        <div v-if="enableWebSearch && filteredHasResults" class="grid grid-cols-2 gap-6">
          <!-- Local Results Column -->
          <div class="space-y-4">
            <div class="flex items-center justify-between mb-4 p-4 bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl border border-emerald-200">
              <div class="flex items-center gap-2">
                <Monitor :size="20" class="text-emerald-600" />
                <h3 class="text-lg font-semibold text-gray-900">本地知识库</h3>
                <span class="px-2 py-1 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium">
                  {{ filteredLocalResults.length }}
                </span>
              </div>
              <div v-if="enableSynonymSearch" class="flex items-center gap-2 px-3 py-1.5 bg-emerald-100 rounded-lg">
                <Sparkles :size="14" class="text-emerald-600" />
                <span class="text-xs text-emerald-700 font-medium">同义词</span>
              </div>
            </div>

            <div v-if="filteredLocalResults.length > 0" class="space-y-4">
              <div
                v-for="(result, index) in filteredLocalResults"
                :key="'local-' + index"
                @click="openDetail(result, 'local')"
                class="bg-white rounded-2xl shadow-md hover:shadow-lg transition-all p-6 border border-gray-200 cursor-pointer hover:border-emerald-300 hover:bg-emerald-50/30"
              >
                <div class="flex items-start gap-3">
                  <div class="w-10 h-10 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-lg flex items-center justify-center flex-shrink-0">
                    <FileText :size="20" class="text-white" />
                  </div>

                  <div class="flex-1">
                    <div class="flex items-center justify-between mb-2">
                      <div class="flex items-center gap-2">
                        <h4 class="font-medium text-gray-900 text-sm truncate">{{ result.source_file }}</h4>
                        <span v-if="enableSynonymSearch" class="px-1.5 py-0.5 bg-emerald-50 text-emerald-600 rounded text-xs">
                          ✨
                        </span>
                      </div>
                      <div class="flex items-center gap-1.5">
                        <div class="flex items-center gap-1 px-2 py-0.5 bg-emerald-50 rounded-md">
                          <Sparkles :size="12" class="text-emerald-600" />
                          <span class="text-xs font-medium text-emerald-700">
                            {{ (result.score * 100).toFixed(1) }}%
                          </span>
                        </div>
                        <ExternalLink :size="14" class="text-gray-400" />
                      </div>
                    </div>

                    <p class="text-gray-600 text-sm leading-relaxed line-clamp-3 break-words">{{ result.content }}</p>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="text-center py-12 bg-gray-50 rounded-xl border border-gray-200">
              <FileText :size="40" class="text-gray-300 mx-auto mb-3" />
              <p class="text-gray-500 text-sm">本地知识库中未找到相关结果</p>
              <p class="text-gray-400 text-xs mt-1">(相似度 ≥50%)</p>
            </div>
          </div>

          <!-- Web Results Column -->
          <div class="space-y-4">
            <div class="flex items-center gap-2 mb-4 p-4 bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl border border-emerald-200">
              <Globe :size="20" class="text-emerald-600" />
              <h3 class="text-lg font-semibold text-gray-900">联网搜索</h3>
              <span class="ml-auto px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-sm font-medium">
                {{ filteredWebResults.length }} 个结果
              </span>
            </div>

            <div v-if="filteredWebResults.length > 0" class="space-y-4">
              <div
                v-for="(result, index) in filteredWebResults"
                :key="'web-' + index"
                @click="openDetail(result, 'web')"
                class="bg-white rounded-2xl shadow-md hover:shadow-lg transition-all p-6 border border-gray-200 cursor-pointer hover:border-emerald-300 hover:bg-emerald-50/30"
              >
                <div class="flex items-start gap-3">
                  <div class="w-10 h-10 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Globe :size="20" class="text-white" />
                  </div>

                  <div class="flex-1">
                    <div class="flex items-center justify-between mb-2">
                      <h4 class="font-medium text-gray-900 text-sm truncate flex-1 mr-2">
                        {{ result.title || result.source_file }}
                      </h4>
                      <div class="flex items-center gap-1.5">
                        <div class="flex items-center gap-1 px-2 py-0.5 bg-emerald-50 rounded-md">
                          <Sparkles :size="12" class="text-emerald-600" />
                          <span class="text-xs font-medium text-emerald-700">
                            {{ (result.score * 100).toFixed(1) }}%
                          </span>
                        </div>
                        <ExternalLink :size="14" class="text-gray-400" />
                      </div>
                    </div>

                    <p class="text-gray-600 text-sm leading-relaxed line-clamp-3 break-words">{{ result.content }}</p>

                    <div v-if="result.source_file && result.source_file.startsWith('http')" class="mt-2 flex items-center gap-1 text-xs text-emerald-600">
                      <ExternalLink :size="12" />
                      <span class="truncate max-w-xs">{{ result.source_file }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="text-center py-12 bg-gray-50 rounded-xl border border-gray-200">
              <Globe :size="40" class="text-gray-300 mx-auto mb-3" />
              <p class="text-gray-500 text-sm">联网搜索未找到相关结果</p>
              <p class="text-gray-400 text-xs mt-1">(相似度 ≥50%)</p>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else-if="!isSearching && searchQuery && !filteredHasResults" class="text-center py-16">
          <div class="w-20 h-20 bg-gradient-to-br from-gray-200 to-gray-300 rounded-3xl flex items-center justify-center mx-auto mb-4">
            <Search :size="40" class="text-gray-500" />
          </div>
          <h3 class="text-xl font-bold text-gray-900 mb-2">未找到相关结果</h3>
          <p class="text-gray-600">尝试使用不同的关键词搜索</p>
        </div>

        <!-- Initial State -->
        <div v-else-if="!isSearching" class="text-center py-16">
          <div class="w-20 h-20 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-3xl flex items-center justify-center mx-auto mb-4 shadow-xl">
            <Search :size="40" class="text-white" />
          </div>
          <h3 class="text-2xl font-bold text-gray-900 mb-2">开始搜索</h3>
          <p class="text-gray-600">输入关键词，在知识库中查找相关内容</p>
        </div>
      </div>
    </div>

    <!-- Detail Modal -->
    <Teleport to="body">
      <div
        v-if="showDetailModal && selectedResult"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
        @click.self="closeDetail"
      >
        <div class="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col">
          <!-- Modal Header -->
          <div class="flex items-center justify-between p-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-white">
            <div class="flex items-center gap-3">
              <div :class="['w-10 h-10 rounded-xl flex items-center justify-center shadow-md bg-gradient-to-br', getResultColor(selectedResultType)]">
                <component :is="getResultIcon(selectedResultType)" :size="20" class="text-white" />
              </div>
              <div>
                <h3 class="text-lg font-semibold text-gray-900">
                  {{ selectedResultType === 'local' ? '本地知识库' : '联网搜索' }} - 详情
                </h3>
                <p class="text-xs text-gray-500">
                  {{ selectedResult.source_file }}
                </p>
              </div>
            </div>
            <button
              @click="closeDetail"
              class="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-gray-100 transition-colors"
            >
              <X :size="20" class="text-gray-500" />
            </button>
          </div>

          <!-- Modal Content -->
          <div class="flex-1 overflow-y-auto p-6">
            <!-- Score Badge -->
            <div class="flex items-center gap-2 mb-4">
              <div class="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-emerald-50 to-teal-50 rounded-lg border border-emerald-200">
                <Sparkles :size="16" class="text-emerald-600" />
                  <span class="text-sm font-semibold text-emerald-700">
                  相似度: {{ (selectedResult.score * 100).toFixed(1) }}%
                </span>
              </div>
              <div v-if="selectedResultType === 'web' && 'source' in selectedResult" class="px-3 py-1.5 bg-emerald-50 rounded-lg border border-emerald-200">
                <span class="text-xs font-medium text-emerald-700">来源: {{ (selectedResult as any).source }}</span>
              </div>
            </div>

            <!-- Content -->
            <div class="prose prose-sm max-w-none">
              <div class="bg-gray-50 rounded-xl p-4 border border-gray-200">
                <h4 class="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                  <Info :size="14" />
                  内容详情
                </h4>
                <div class="text-gray-700 leading-relaxed markdown-content break-words" v-html="renderMarkdown(selectedResult.content)"></div>
              </div>

              <!-- Web Link -->
              <div v-if="selectedResultType === 'web' && selectedResult.source_file && selectedResult.source_file.startsWith('http')" class="mt-4">
                <a
                  :href="selectedResult.source_file"
                  target="_blank"
                  class="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-lg hover:from-emerald-700 hover:to-teal-700 transition-all shadow-md"
                >
                  <ExternalLink :size="16" />
                  <span>访问原文链接</span>
                </a>
              </div>

              <!-- Metadata -->
              <div v-if="selectedResultType === 'local'" class="mt-6 p-4 bg-emerald-50 rounded-xl border border-emerald-200">
                <h4 class="text-sm font-semibold text-emerald-800 mb-3 flex items-center gap-2">
                  <Database :size="14" />
                  元信息
                </h4>
                <div class="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span class="text-emerald-600 font-medium">文档 ID:</span>
                    <p class="text-gray-700 font-mono text-xs mt-1 break-all">{{ (selectedResult as SearchResult).document_id }}</p>
                  </div>
                  <div>
                    <span class="text-emerald-600 font-medium">片段 ID:</span>
                    <p class="text-gray-700 font-mono text-xs mt-1 break-all">{{ selectedResult.chunk_id }}</p>
                  </div>
                  <div v-if="(selectedResult as SearchResult).page_number">
                    <span class="text-emerald-600 font-medium">页码:</span>
                    <p class="text-gray-700 mt-1">{{ (selectedResult as SearchResult).page_number }}</p>
                  </div>
                  <div>
                    <span class="text-emerald-600 font-medium">来源文件:</span>
                    <p class="text-gray-700 mt-1">{{ selectedResult.source_file }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Modal Footer -->
          <div class="flex items-center justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50">
            <button
              @click="closeDetail"
              class="px-6 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              关闭
            </button>
            <button
              @click="closeDetail"
              class="px-6 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-lg hover:from-emerald-700 hover:to-teal-700 transition-all shadow-md"
            >
              确定
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.break-words {
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-word;
}

.markdown-content {
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-word;
  max-width: 100%;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4),
.markdown-content :deep(h5),
.markdown-content :deep(h6) {
  margin-top: 1em;
  margin-bottom: 0.5em;
  font-weight: 600;
  line-height: 1.3;
  color: #1f2937;
}

.markdown-content :deep(h1) { font-size: 1.5em; }
.markdown-content :deep(h2) { font-size: 1.25em; }
.markdown-content :deep(h3) { font-size: 1.1em; }
.markdown-content :deep(h4) { font-size: 1em; }

.markdown-content :deep(p) {
  margin: 0.5em 0;
  line-height: 1.6;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.markdown-content :deep(li) {
  margin: 0.25em 0;
}

.markdown-content :deep(code) {
  background-color: #f1f5f9;
  padding: 0.125em 0.375em;
  border-radius: 0.25em;
  font-size: 0.875em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #dc2626;
  word-wrap: break-word;
}

.markdown-content :deep(pre) {
  background-color: #1e293b;
  color: #e2e8f0;
  padding: 1em;
  border-radius: 0.5em;
  overflow-x: auto;
  margin: 0.75em 0;
}

.markdown-content :deep(pre code) {
  background-color: transparent;
  color: inherit;
  padding: 0;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid #cbd5e1;
  padding-left: 1em;
  margin: 0.75em 0;
  color: #64748b;
  font-style: italic;
}

.markdown-content :deep(a) {
  color: #3b82f6;
  text-decoration: underline;
}

.markdown-content :deep(a:hover) {
  color: #2563eb;
}

.markdown-content :deep(hr) {
  border: none;
  border-top: 1px solid #e2e8f0;
  margin: 1em 0;
}

.markdown-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.75em 0;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid #e2e8f0;
  padding: 0.5em;
  text-align: left;
}

.markdown-content :deep(th) {
  background-color: #f8fafc;
  font-weight: 600;
}

.markdown-content :deep(img) {
  max-width: 100%;
  height: auto;
}

.markdown-content :deep(strong) {
  font-weight: 600;
  color: #1f2937;
}

.markdown-content :deep(em) {
  font-style: italic;
}

.markdown-content :deep(del) {
  text-decoration: line-through;
  color: #94a3b8;
}
</style>
