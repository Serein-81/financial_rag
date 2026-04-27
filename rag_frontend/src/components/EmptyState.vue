<script setup lang="ts">
import type { FunctionalComponent, SVGAttributes } from 'vue'

interface Props {
  icon: FunctionalComponent<SVGAttributes>
  title: string
  description?: string
  actionLabel?: string
  actionTo?: string
}

withDefaults(defineProps<Props>(), {})

const emit = defineEmits<{
  action: []
}>()
</script>

<template>
  <div class="h-full flex items-center justify-center p-8">
    <div class="text-center max-w-sm">
      <div class="relative inline-flex mb-6">
        <div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center ring-1 ring-inset ring-slate-200/50">
          <component :is="icon" :size="36" class="text-slate-400" />
        </div>
        <div class="absolute -bottom-1 -right-1 w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
        </div>
      </div>
      <h3 class="text-xl font-bold text-slate-800 mb-2">{{ title }}</h3>
      <p v-if="description" class="text-sm text-slate-500 mb-6 leading-relaxed max-w-xs mx-auto">{{ description }}</p>
      <router-link
        v-if="actionLabel && actionTo"
        :to="actionTo"
        class="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all shadow-md hover:shadow-lg font-medium text-sm hover:-translate-y-0.5 active:translate-y-0"
      >
        {{ actionLabel }}
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
      </router-link>
      <button
        v-else-if="actionLabel"
        @click="emit('action')"
        class="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all shadow-md hover:shadow-lg font-medium text-sm hover:-translate-y-0.5 active:translate-y-0"
      >
        {{ actionLabel }}
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
      </button>
    </div>
  </div>
</template>
