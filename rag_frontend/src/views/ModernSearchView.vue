<script setup lang="ts">
import { ref, computed } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { Search, Database, FileText, Sparkles, Loader2, Globe, Monitor, ToggleLeft, ToggleRight, X, ExternalLink, AlertCircle, CheckCircle, Info, ChevronDown, ChevronUp, Sliders, Cpu, BookOpen, Type } from 'lucide-vue-next'
import { request } from '@/utils/request'
import { searchApi, type SearchResult, type WebSearchResult } from '@/api/search'
import { marked } from 'marked'
import PageHeader from '@/components/PageHeader.vue'
import ResultCard from '@/components/ResultCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import SkeletonCard from '@/components/SkeletonCard.vue'

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
  <div class="flex-1 flex flex-col h-full bg-gradient-to-br from-slate-100 via-emerald-50/30 to-teal-50/30">
    <PageHeader
      :icon="Search"
      title="语义搜索"
      subtitle="在知识库中搜索相关内容"
    >
      <div class="flex items-center gap-2 px-4 py-2 bg-white rounded-xl border border-slate-200 shadow-sm">
        <Database :size="16" class="text-slate-400" />
        <select
          v-model="knowledgeStore.selectedKnowledgeBaseId"
          class="bg-transparent text-sm text-slate-700 outline-none cursor-pointer min-w-[120px]"
        >
          <option :value="null">所有知识库</option>
          <option v-for="kb in knowledgeStore.knowledgeBases" :key="kb.id" :value="kb.id">
            {{ kb.name }}
          </option>
        </select>
      </div>
    </PageHeader>

    <div class="flex-1 overflow-y-auto">
      <div class="max-w-5xl mx-auto p-6 space-y-6">
        <!-- Search Box -->
        <div class="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm">
          <div class="flex gap-3">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="输入你想搜索的内容..."
              class="flex-1 px-5 py-3.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:bg-white focus:border-emerald-400 focus:ring-4 focus:ring-emerald-100 transition-all outline-none text-base"
              @keydown.enter="handleSearch"
            />
            <button
              @click="handleSearch"
              :disabled="isSearching || !searchQuery.trim()"
              class="px-7 py-3.5 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg hover:shadow-xl flex items-center gap-2.5 font-medium text-sm"
            >
              <Search :size="18" v-if="!isSearching" />
              <Loader2 :size="18" class="animate-spin" v-else />
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
                class="flex-1 flex items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer transition-all duration-300 relative overflow-hidden"
                :class="enableWebSearch
                  ? 'border-emerald-300 bg-gradient-to-br from-emerald-50/80 to-teal-50/50 shadow-sm'
                  : 'border-slate-200 bg-white/50 hover:border-slate-300 hover:bg-slate-50/50'"
              >
                <!-- Active glow -->
                <div v-if="enableWebSearch" class="absolute inset-0 bg-gradient-to-r from-emerald-500/5 to-teal-500/5 pointer-events-none" />

                <div class="relative flex items-center gap-3 w-full">
                  <div
                    :class="[
                      'w-10 h-10 rounded-lg flex items-center justify-center shadow-sm transition-all duration-300',
                      enableWebSearch ? 'bg-gradient-to-br from-emerald-500 to-teal-600 shadow-emerald-200' : 'bg-slate-300'
                    ]"
                  >
                    <Globe :size="20" class="text-white" />
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="font-medium text-sm" :class="enableWebSearch ? 'text-emerald-900' : 'text-slate-700'">联网搜索</span>
                      <span v-if="enableWebSearch" class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700">已开启</span>
                    </div>
                    <div class="text-xs" :class="enableWebSearch ? 'text-emerald-600' : 'text-slate-500'">实时获取互联网信息</div>
                  </div>

                  <!-- Toggle Switch -->
                  <div
                    :class="[
                      'relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0',
                      enableWebSearch ? 'bg-gradient-to-r from-emerald-500 to-teal-500' : 'bg-slate-300'
                    ]"
                  >
                    <div
                      class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-md transition-all duration-300"
                      :class="enableWebSearch ? 'translate-x-5' : 'translate-x-0'"
                    />
                  </div>
                </div>
              </div>

              <!-- Synonym Search Toggle -->
              <div
                @click="enableSynonymSearch = !enableSynonymSearch"
                class="flex-1 flex items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer transition-all duration-300 relative overflow-hidden"
                :class="enableSynonymSearch
                  ? 'border-emerald-300 bg-gradient-to-br from-emerald-50/80 to-green-50/50 shadow-sm'
                  : 'border-slate-200 bg-white/50 hover:border-slate-300 hover:bg-slate-50/50'"
              >
                <div v-if="enableSynonymSearch" class="absolute inset-0 bg-gradient-to-r from-emerald-500/5 to-green-500/5 pointer-events-none" />

                <div class="relative flex items-center gap-3 w-full">
                  <div
                    :class="[
                      'w-10 h-10 rounded-lg flex items-center justify-center shadow-sm transition-all duration-300',
                      enableSynonymSearch ? 'bg-gradient-to-br from-emerald-500 to-green-600 shadow-emerald-200' : 'bg-slate-300'
                    ]"
                  >
                    <Sparkles :size="20" class="text-white" />
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="font-medium text-sm" :class="enableSynonymSearch ? 'text-emerald-900' : 'text-slate-700'">同义词扩展</span>
                      <span v-if="enableSynonymSearch" class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700">已开启</span>
                    </div>
                    <div class="text-xs" :class="enableSynonymSearch ? 'text-emerald-600' : 'text-slate-500'">智能匹配相关词汇</div>
                  </div>

                  <div
                    :class="[
                      'relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0',
                      enableSynonymSearch ? 'bg-gradient-to-r from-emerald-500 to-green-500' : 'bg-slate-300'
                    ]"
                  >
                    <div
                      class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-md transition-all duration-300"
                      :class="enableSynonymSearch ? 'translate-x-5' : 'translate-x-0'"
                    />
                  </div>
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
              class="p-5 bg-gradient-to-br from-white to-emerald-50/30 rounded-xl border border-emerald-200/60 shadow-sm space-y-5"
            >
              <div class="flex items-center gap-2 pb-3 border-b border-emerald-200/40">
                <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
                  <Sliders :size="14" class="text-white" />
                </div>
                <span class="text-sm font-semibold text-slate-800">搜索权重配置</span>
              </div>

              <!-- Vector Weight -->
              <div class="space-y-2">
                <div class="flex items-center justify-between text-sm">
                  <div class="flex items-center gap-2">
                    <Cpu :size="14" class="text-emerald-600" />
                    <span class="text-slate-600 font-medium">向量搜索权重</span>
                  </div>
                  <span class="font-semibold gradient-text bg-gradient-to-r from-emerald-600 to-teal-600">{{ (vectorWeight * 100).toFixed(0) }}%</span>
                </div>
                <input
                  type="range"
                  v-model.number="vectorWeight"
                  min="0"
                  max="1"
                  step="0.1"
                  class="w-full h-2 bg-emerald-200/60 rounded-full appearance-none cursor-pointer accent-emerald-600 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-gradient-to-r [&::-webkit-slider-thumb]:from-emerald-500 [&::-webkit-slider-thumb]:to-teal-600 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:cursor-pointer"
                />
                <div class="flex justify-between text-xs text-slate-400">
                  <span>注重语义理解</span>
                  <span>注重精确匹配</span>
                </div>
              </div>

              <!-- Synonym Weight -->
              <div class="space-y-2">
                <div class="flex items-center justify-between text-sm">
                  <div class="flex items-center gap-2">
                    <BookOpen :size="14" class="text-emerald-600" />
                    <span class="text-slate-600 font-medium">同义词权重</span>
                  </div>
                  <span class="font-semibold gradient-text bg-gradient-to-r from-emerald-600 to-teal-600">{{ (synonymWeight * 100).toFixed(0) }}%</span>
                </div>
                <input
                  type="range"
                  v-model.number="synonymWeight"
                  min="0"
                  max="1"
                  step="0.1"
                  class="w-full h-2 bg-emerald-200/60 rounded-full appearance-none cursor-pointer accent-emerald-600 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-gradient-to-r [&::-webkit-slider-thumb]:from-emerald-500 [&::-webkit-slider-thumb]:to-teal-600 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:cursor-pointer"
                />
                <div class="flex justify-between text-xs text-slate-400">
                  <span>注重原词匹配</span>
                  <span>注重同义词扩展</span>
                </div>
              </div>

              <!-- Fulltext Weight -->
              <div class="space-y-2">
                <div class="flex items-center justify-between text-sm">
                  <div class="flex items-center gap-2">
                    <Type :size="14" class="text-emerald-600" />
                    <span class="text-slate-600 font-medium">全文搜索权重</span>
                  </div>
                  <span class="font-semibold gradient-text bg-gradient-to-r from-emerald-600 to-teal-600">{{ (fulltextWeight * 100).toFixed(0) }}%</span>
                </div>
                <input
                  type="range"
                  v-model.number="fulltextWeight"
                  min="0"
                  max="1"
                  step="0.1"
                  class="w-full h-2 bg-emerald-200/60 rounded-full appearance-none cursor-pointer accent-emerald-600 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-gradient-to-r [&::-webkit-slider-thumb]:from-emerald-500 [&::-webkit-slider-thumb]:to-teal-600 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:cursor-pointer"
                />
                <div class="flex justify-between text-xs text-slate-400">
                  <span>注重模糊匹配</span>
                  <span>注重精确短语</span>
                </div>
              </div>

              <!-- Weight Summary -->
              <div class="pt-3 border-t border-emerald-200/40">
                <div class="text-xs text-slate-500 text-center bg-white/60 rounded-lg py-2">
                  当前权重配置：向量 <span class="font-semibold text-emerald-600">{{ (vectorWeight * 100).toFixed(0) }}%</span>
                  · 同义词 <span class="font-semibold text-emerald-600">{{ (synonymWeight * 100).toFixed(0) }}%</span>
                  · 全文 <span class="font-semibold text-emerald-600">{{ (fulltextWeight * 100).toFixed(0) }}%</span>
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

        <!-- Loading State -->
        <div v-if="isSearching" class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SkeletonCard v-for="i in 4" :key="i" :lines="2" :hasHeader="true" />
        </div>

        <!-- Single Column Results (Local Only) -->
        <div v-else-if="(!enableWebSearch || (enableWebSearch && !filteredWebResults.length && filteredLocalResults.length > 0)) && filteredLocalResults.length > 0" class="space-y-3">
          <div class="flex items-center gap-3 px-4 py-2.5 bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl border border-emerald-200/60">
            <Monitor :size="16" class="text-emerald-600" />
            <h3 class="text-sm font-semibold text-slate-800">本地知识库结果</h3>
            <span class="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium">
              {{ filteredLocalResults.length }} 个结果
            </span>
            <span v-if="enableSynonymSearch" class="ml-auto flex items-center gap-1 text-xs text-emerald-600 font-medium">
              <Sparkles :size="12" />
              同义词
            </span>
          </div>

          <ResultCard
            v-for="(result, index) in filteredLocalResults"
            :key="'local-' + index"
            :title="result.source_file"
            :content="result.content"
            :score="result.score"
            :badge="enableSynonymSearch ? '同义词' : undefined"
            :metaLine="result.images?.length ? `🖼️ 含 ${result.images.length} 张图片，点击查看原图` : undefined"
            type="local"
            @click="openDetail(result, 'local')"
          />
        </div>

        <!-- Dual Column Results (Local + Web) -->
        <div v-else-if="enableWebSearch && filteredHasResults" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div class="space-y-3">
            <div class="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl border border-emerald-200/60">
              <Monitor :size="16" class="text-emerald-600" />
              <h3 class="text-sm font-semibold text-slate-800">本地知识库</h3>
              <span class="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium">
                {{ filteredLocalResults.length }}
              </span>
              <span v-if="enableSynonymSearch" class="ml-auto flex items-center gap-1 text-xs text-emerald-600 font-medium">
                <Sparkles :size="12" />同义词
              </span>
            </div>

            <ResultCard
              v-for="(result, index) in filteredLocalResults"
              :key="'dual-local-' + index"
              :title="result.source_file"
              :content="result.content"
              :score="result.score"
              :badge="enableSynonymSearch ? '同义词' : undefined"
              type="local"
              @click="openDetail(result, 'local')"
            />

            <div v-if="filteredLocalResults.length === 0" class="py-10 bg-slate-50 rounded-xl border border-slate-100 text-center">
              <FileText :size="32" class="text-slate-300 mx-auto mb-2" />
              <p class="text-slate-500 text-sm">本地知识库中未找到相关结果</p>
            </div>
          </div>

          <div class="space-y-3">
            <div class="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-sky-50 to-blue-50 rounded-xl border border-sky-200/60">
              <Globe :size="16" class="text-sky-600" />
              <h3 class="text-sm font-semibold text-slate-800">联网搜索</h3>
              <span class="ml-auto px-2 py-0.5 bg-sky-100 text-sky-700 rounded-full text-xs font-medium">
                {{ filteredWebResults.length }} 个结果
              </span>
            </div>

            <ResultCard
              v-for="(result, index) in filteredWebResults"
              :key="'web-' + index"
              :title="result.title || result.source_file"
              :content="result.content"
              :score="result.score"
              :meta-line="result.source_file && result.source_file.startsWith('http') ? result.source_file : undefined"
              type="web"
              @click="openDetail(result, 'web')"
            />

            <div v-if="filteredWebResults.length === 0" class="py-10 bg-slate-50 rounded-xl border border-slate-100 text-center">
              <Globe :size="32" class="text-slate-300 mx-auto mb-2" />
              <p class="text-slate-500 text-sm">联网搜索未找到相关结果</p>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <EmptyState
          v-else-if="!isSearching && searchQuery && !filteredHasResults"
          :icon="Search"
          title="未找到相关结果"
          description="尝试使用不同的关键词搜索"
        />

        <!-- Initial State -->
        <EmptyState
          v-else-if="!isSearching"
          :icon="Search"
          title="开始搜索"
          description="输入关键词，在知识库中查找相关内容"
        />
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

              <!-- 原始图片 -->
              <div
                v-if="selectedResultType === 'local' && (selectedResult as SearchResult).images?.length"
                class="mt-6"
              >
                <h4 class="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                  <span>🖼️</span> 原始图片
                </h4>
                <div class="grid grid-cols-1 gap-4">
                  <div
                    v-for="(img, idx) in (selectedResult as SearchResult).images"
                    :key="idx"
                    class="rounded-xl border border-slate-200 overflow-hidden bg-slate-50"
                  >
                    <img
                      v-if="img.url"
                      :src="img.url"
                      :alt="img.description || '图片'"
                      class="w-full max-h-96 object-contain bg-white"
                      loading="lazy"
                    />
                    <div v-else class="flex items-center justify-center h-20 text-slate-400 text-sm">
                      图片加载失败
                    </div>
                    <div v-if="img.description" class="px-3 py-2 text-xs text-slate-500 border-t border-slate-100">
                      {{ img.description }}
                    </div>
                    <div v-if="img.page" class="px-3 pb-2 text-xs text-slate-400">第 {{ img.page }} 页</div>
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
