<script setup lang="ts">
import type { FunctionalComponent, SVGAttributes } from 'vue'

interface Props {
  icon: FunctionalComponent<SVGAttributes>
  title: string
  subtitle?: string
  iconGradient?: string
}

withDefaults(defineProps<Props>(), {
  iconGradient: 'from-emerald-600 to-teal-600'
})
</script>

<template>
  <div class="h-16 bg-white/80 backdrop-blur-sm border-b border-slate-200/80 flex items-center justify-between px-6">
    <div class="flex items-center gap-3.5">
      <div
        :class="[
          'w-10 h-10 rounded-xl flex items-center justify-center shadow-sm flex-shrink-0 transition-transform duration-300 hover:scale-105',
          'bg-gradient-to-br',
          iconGradient
        ]"
      >
        <component :is="icon" :size="20" class="text-white" />
      </div>
      <div class="flex flex-col gap-0.5">
        <h2 class="text-base font-semibold text-slate-900 leading-none">{{ title }}</h2>
        <p v-if="subtitle" class="text-xs text-slate-500 leading-none font-medium">{{ subtitle }}</p>
      </div>
    </div>
    <slot />
  </div>
</template>
