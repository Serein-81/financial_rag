<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  title?: string
  sourceFile?: string
  content: string
  score?: number
  type?: 'local' | 'web'
  badge?: string
  metaLine?: string
}

const props = withDefaults(defineProps<Props>(), {
  type: 'local'
})

const emit = defineEmits<{
  click: []
}>()

const scorePercent = computed(() =>
  props.score !== undefined ? `${(props.score * 100).toFixed(0)}%` : null
)

const scoreColor = computed(() => {
  if (props.score === undefined) return 'bg-slate-100 text-slate-500'
  if (props.score >= 0.8) return 'bg-emerald-100 text-emerald-700'
  if (props.score >= 0.6) return 'bg-emerald-50 text-emerald-600'
  if (props.score >= 0.4) return 'bg-amber-50 text-amber-600'
  return 'bg-red-50 text-red-600'
})

const progressWidth = computed(() =>
  props.score !== undefined ? `${Math.round(props.score * 100)}%` : '0%'
)

const iconGradient = computed(() =>
  props.type === 'web'
    ? 'from-sky-500 to-blue-600'
    : 'from-emerald-500 to-teal-600'
)

const typeIcon = computed(() => {
  if (props.type === 'web') {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`
})
</script>

<template>
  <div
    @click="emit('click')"
    class="group relative bg-white rounded-2xl border border-slate-200/80 p-5 cursor-pointer transition-all duration-300 hover:shadow-xl hover:border-emerald-300/60 hover:-translate-y-0.5"
  >
    <div class="absolute inset-0 rounded-2xl bg-gradient-to-br from-emerald-50/40 to-teal-50/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />

    <div class="relative flex items-start gap-4">
      <div
        :class="[
          'w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm transition-transform duration-300 group-hover:scale-110 group-hover:shadow-md',
          'bg-gradient-to-br',
          iconGradient
        ]"
        v-html="typeIcon"
        class="[&>svg]:text-white"
      />

      <div class="flex-1 min-w-0">
        <div class="flex items-center justify-between gap-3 mb-2">
          <div class="flex items-center gap-2 min-w-0">
            <h3 class="text-sm font-semibold text-slate-800 truncate">
              {{ title || sourceFile || (type === 'web' ? '网页结果' : '文档片段') }}
            </h3>
            <span
              v-if="badge"
              class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-xs font-medium bg-emerald-50 text-emerald-600 flex-shrink-0"
            >
              {{ badge }}
            </span>
          </div>
          <div
            v-if="scorePercent"
            :class="[
              'inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold flex-shrink-0 transition-all duration-300',
              scoreColor,
              'group-hover:shadow-sm'
            ]"
          >
            {{ scorePercent }}
          </div>
        </div>

        <div v-if="score !== undefined" class="mb-2.5">
          <div class="h-1 bg-slate-100 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-700 ease-out bg-gradient-to-r from-emerald-400 to-teal-500"
              :style="{ width: progressWidth }"
            />
          </div>
        </div>

        <p class="text-sm text-slate-600 leading-relaxed line-clamp-3 break-words">{{ content }}</p>

        <div v-if="metaLine" class="flex items-center gap-2 mt-3 pt-3 border-t border-slate-100">
          <span class="text-xs text-slate-400">{{ metaLine }}</span>
        </div>
      </div>

      <div class="flex-shrink-0 self-center opacity-0 group-hover:opacity-100 transition-all duration-200 group-hover:translate-x-0.5">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-emerald-400"><path d="m9 18 6-6-6-6"/></svg>
      </div>
    </div>
  </div>
</template>
