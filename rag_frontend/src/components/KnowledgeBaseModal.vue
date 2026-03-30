<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { XMarkIcon, PlusIcon, TrashIcon, FolderIcon } from '@heroicons/vue/24/outline'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useI18n } from 'vue-i18n'

const emit = defineEmits<{
  close: []
}>()

const knowledgeStore = useKnowledgeStore()
const { t } = useI18n()

const isOpen = defineModel<boolean>('isOpen', { default: false })
const newKBName = ref('')
const isCreating = ref(false)

// 计算属性：是否有选中的知识库
const hasSelectedKB = computed(() => knowledgeStore.selectedKnowledgeBase !== null)

async function handleCreateKB() {
  if (!newKBName.value.trim()) {
    alert('请输入知识库名称')
    return
  }

  try {
    isCreating.value = true
    await knowledgeStore.createKnowledgeBase({
      name: newKBName.value.trim(),
      description: '',
    })
    newKBName.value = ''
  } catch (error) {
    console.error('创建知识库失败:', error)
    alert('创建知识库失败，请重试')
  } finally {
    isCreating.value = false
  }
}

async function handleDeleteKB(kbId: string, kbName: string) {
  if (!confirm(`确定要删除知识库 "${kbName}" 吗？此操作不可恢复。`)) {
    return
  }

  try {
    await knowledgeStore.deleteKnowledgeBase(kbId)
    // 如果删除的是当前选中的知识库，清除选中状态
    if (knowledgeStore.selectedKnowledgeBaseId === kbId) {
      knowledgeStore.selectedKnowledgeBaseId = null
    }
  } catch (error) {
    console.error('删除知识库失败:', error)
    alert('删除知识库失败，请重试')
  }
}

function handleSelectKB(kbId: string) {
  knowledgeStore.selectedKnowledgeBaseId = kbId
  emit('close')
}

// 监听弹窗打开，刷新知识库列表
watch(isOpen, async (newVal) => {
  if (newVal) {
    try {
      await knowledgeStore.fetchKnowledgeBases()
    } catch (error) {
      console.error('获取知识库列表失败:', error)
    }
  }
})
</script>

<template>
  <!-- 背景遮罩 -->
  <Transition
    enter-active-class="transition ease-out duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition ease-in duration-150"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="isOpen"
      @click="emit('close')"
      class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50"
    />
  </Transition>

  <!-- 弹窗 -->
  <Transition
    enter-active-class="transition ease-out duration-200"
    enter-from-class="opacity-0 scale-95"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition ease-in duration-150"
    leave-from-class="opacity-100 scale-100"
    leave-to-class="opacity-0 scale-95"
  >
    <div
      v-if="isOpen"
      @click.stop
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <div
        :class="[
          'w-full max-w-2xl rounded-2xl shadow-2xl',
          'bg-white dark:bg-zinc-900',
          'border border-zinc-200 dark:border-zinc-800'
        ]"
      >
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-5 border-b border-zinc-200 dark:border-zinc-800">
          <h2 class="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            知识库管理
          </h2>
          <button
            @click="emit('close')"
            class="p-2 rounded-lg text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <XMarkIcon class="w-5 h-5" />
          </button>
        </div>

        <!-- Content -->
        <div class="p-6 space-y-6">
          <!-- 创建新知识库 -->
          <div>
            <h3 class="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-3">
              创建新知识库
            </h3>
            <div class="flex gap-3">
              <input
                v-model="newKBName"
                type="text"
                placeholder="输入知识库名称"
                :disabled="isCreating"
                class="flex-1 px-4 py-2.5 rounded-xl text-sm focus:outline-none transition-all duration-200 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 border border-zinc-200 dark:border-zinc-700 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 placeholder:text-zinc-400 dark:placeholder:text-zinc-600"
              />
              <button
                @click="handleCreateKB"
                :disabled="isCreating || !newKBName.trim()"
                :class="[
                  'px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                  'bg-gradient-to-r from-indigo-500 to-violet-500 hover:from-indigo-600 hover:to-violet-600',
                  'text-white',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                ]"
              >
                <div class="flex items-center gap-2">
                  <PlusIcon v-if="!isCreating" class="w-4 h-4" />
                  <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>{{ isCreating ? '创建中...' : '创建' }}</span>
                </div>
              </button>
            </div>
          </div>

          <!-- 知识库列表 -->
          <div>
            <h3 class="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-3">
              已有知识库
            </h3>
            <div class="space-y-2 max-h-80 overflow-y-auto scrollbar-custom">
              <!-- 空状态 -->
              <div
                v-if="knowledgeStore.knowledgeBases.length === 0"
                class="text-center py-8 text-zinc-500 dark:text-zinc-400"
              >
                <FolderIcon class="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p class="text-sm">暂无知识库</p>
              </div>

              <!-- 知识库列表 -->
              <div
                v-else
                v-for="kb in knowledgeStore.knowledgeBases"
                :key="kb.id"
                :class="[
                  'flex items-center justify-between p-4 rounded-xl transition-all duration-200',
                  knowledgeStore.selectedKnowledgeBaseId === kb.id
                    ? 'bg-indigo-50 dark:bg-indigo-900/20 border-2 border-indigo-500'
                    : 'bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600'
                ]"
              >
                <div class="flex-1">
                  <div class="flex items-center gap-3">
                    <FolderIcon
                      :class="[
                        'w-5 h-5',
                        knowledgeStore.selectedKnowledgeBaseId === kb.id
                          ? 'text-indigo-500'
                          : 'text-zinc-500 dark:text-zinc-400'
                      ]"
                    />
                    <div>
                      <p
                        :class="[
                          'text-sm font-medium',
                          knowledgeStore.selectedKnowledgeBaseId === kb.id
                            ? 'text-indigo-700 dark:text-indigo-300'
                            : 'text-zinc-900 dark:text-zinc-100'
                        ]"
                      >
                        {{ kb.name }}
                      </p>
                      <p
                        v-if="kb.description"
                        :class="[
                          'text-xs mt-0.5',
                          knowledgeStore.selectedKnowledgeBaseId === kb.id
                            ? 'text-indigo-600 dark:text-indigo-400'
                            : 'text-zinc-500 dark:text-zinc-400'
                        ]"
                      >
                        {{ kb.description }}
                      </p>
                    </div>
                  </div>
                </div>

                <div class="flex items-center gap-2">
                  <!-- 选中状态指示 -->
                  <div
                    v-if="knowledgeStore.selectedKnowledgeBaseId === kb.id"
                    class="w-2 h-2 rounded-full bg-indigo-500"
                  />

                  <!-- 选择按钮 -->
                  <button
                    v-else
                    @click="handleSelectKB(kb.id)"
                    class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 bg-indigo-500 text-white hover:bg-indigo-600"
                  >
                    选择
                  </button>

                  <!-- 删除按钮 -->
                  <button
                    @click="handleDeleteKB(kb.id, kb.name)"
                    class="p-1.5 rounded-lg text-zinc-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                  >
                    <TrashIcon class="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="px-6 py-4 border-t border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50 rounded-b-2xl">
          <p class="text-xs text-zinc-500 dark:text-zinc-400 text-center">
            提示：删除知识库将同时删除该知识库下的所有文档，请谨慎操作
          </p>
        </div>
      </div>
    </div>
  </Transition>
</template>
