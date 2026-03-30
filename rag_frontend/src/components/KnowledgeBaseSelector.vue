<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { Database, ChevronDown, Plus } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

const knowledgeStore = useKnowledgeStore()
const { t } = useI18n()

const emit = defineEmits<{
  create: []
}>()

const kbDropdown = ref<HTMLElement>()
const isOpen = ref(false)

const selectedKB = computed(() => knowledgeStore.selectedKnowledgeBase)
const selectedKBText = computed(() => {
  const kb = selectedKB.value
  return kb ? kb.name : t('sidebar.selectKnowledgeBase')
})

const isOpenText = computed(() => isOpen.value ? t('sidebar.close') : t('sidebar.selectKnowledgeBase'))

function toggleDropdown() {
  isOpen.value = !isOpen.value
}

function closeDropdown() {
  isOpen.value = false
}

function handleSelectKB(kb_id: string) {
  knowledgeStore.selectKnowledgeBase(kb_id)
  // 选择后自动收起下拉
  isOpen.value = false
}

function handleCreateKB() {
  emit('create')
  // 创建后自动收起下拉
  isOpen.value = false
}

// 点击外部关闭下拉
onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

function handleClickOutside(event: Event) {
  if (kbDropdown.value && !kbDropdown.value.contains(event.target as Node)) {
    isOpen.value = false
  }
}
</script>

<template>
  <div class="relative">
    <button
      @click="toggleDropdown"
      class="w-full px-3 py-2 bg-white border border-gray-200 text-slate-600 text-xs font-mono hover:border-blue-600 hover:text-blue-600 transition-all duration-200 rounded-sm flex items-center justify-between"
    >
      <div class="flex items-center gap-2">
        <Database :size="14" class="text-slate-500" />
        <span class="truncate flex-1">{{ selectedKBText }}</span>
        <ChevronDown :size="14" :class="{ 'rotate-180': isOpen }" />
      </div>
    </button>

    <!-- Dropdown -->
    <div
      v-show="isOpen"
      ref="kbDropdown"
      class="absolute top-full left-0 w-full mt-1 bg-white border border-gray-200 shadow-lg z-50"
    >
      <div class="py-1">
        <!-- Knowledge Bases List -->
        <div class="max-h-60 overflow-y-auto scrollbar-custom">
          <div v-if="knowledgeStore.knowledgeBases.length === 0" class="px-3 py-4 text-center text-slate-500 text-xs font-mono">
            {{ t('sidebar.noKnowledgeBases') }}
          </div>

          <button
            v-for="kb in knowledgeStore.knowledgeBases"
            :key="kb.id"
            @click="handleSelectKB(kb.id)"
            class="w-full px-3 py-2 text-left text-xs font-mono hover:bg-gray-50 transition-colors flex items-center gap-3"
            :class="[
              selectedKB?.id === kb.id
                ? 'bg-blue-50 text-blue-600'
                : 'text-slate-600'
            ]"
          >
            <Database :size="14" :class="selectedKB?.id === kb.id ? 'text-blue-600' : 'text-slate-500'" />
            <span class="truncate flex-1">{{ kb.name }}</span>
            <div v-if="selectedKB?.id === kb.id" class="w-1 h-1 bg-blue-600 rounded-sm" />
          </button>
        </div>
      </div>

      <!-- Create New KB Button -->
      <div class="border-t border-gray-200">
        <button
          @click="handleCreateKB"
          class="w-full px-3 py-2 text-left text-xs font-mono text-blue-600 hover:bg-gray-50 transition-colors flex items-center gap-2"
        >
          <Plus :size="14" />
          <span>{{ t('sidebar.createKnowledgeBase') }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
