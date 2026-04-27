<script setup lang="ts">
import type { FunctionalComponent, SVGAttributes } from 'vue'
import { computed } from 'vue'

interface Props {
  icon: FunctionalComponent<SVGAttributes>
  label: string
  value: string | number
  trend?: number
  trendLabel?: string
  iconGradient?: string
  accentColor?: string
  subLabel?: string
  subValue?: string | number
  badge?: string
  badgeColor?: string
}

const props = withDefaults(defineProps<Props>(), {
  iconGradient: 'from-emerald-500 to-teal-600',
  accentColor: 'emerald',
  badgeColor: 'bg-slate-100 text-slate-600'
})

const trendSign = computed(() => props.trend !== undefined ? (props.trend > 0 ? '+' : '') : '')

const trendColorClass = computed(() => {
  if (props.trend === undefined) return ''
  return props.trend > 0 ? 'text-emerald-600 bg-emerald-50' : 'text-red-600 bg-red-50'
})
</script>

<template>
  <div
    class="group relative bg-white rounded-2xl border border-slate-200/80 p-5 transition-all duration-300 hover:shadow-xl hover:border-slate-300/80 hover:-translate-y-0.5"
  >
    <!-- Subtle gradient overlay on hover -->
    <div class="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />

    <div class="relative">
      <div class="flex items-center justify-between mb-4">
        <div
          :class="[
            'w-11 h-11 rounded-xl flex items-center justify-center shadow-sm transition-transform duration-300 group-hover:scale-110 group-hover:shadow-md',
            'bg-gradient-to-br',
            iconGradient
          ]"
        >
          <component :is="icon" :size="20" class="text-white" />
        </div>
        <span
          v-if="trend !== undefined"
          :class="[
            'inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold transition-all duration-300',
            trendColorClass,
            'group-hover:shadow-sm'
          ]"
        >
          <svg v-if="trend > 0" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>
          <svg v-else-if="trend < 0" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
          <span>{{ trendSign }}{{ trend }}%</span>
        </span>
        <span
          v-else-if="badge"
          :class="[
            'inline-flex items-center px-2 py-1 rounded-lg text-xs font-medium',
            badgeColor
          ]"
        >
          {{ badge }}
        </span>
      </div>

      <p class="text-2xl font-bold text-slate-900 mb-1 tabular-nums tracking-tight">{{ value }}</p>
      <p class="text-sm text-slate-500">{{ label }}</p>

      <div v-if="subLabel || trendLabel" class="mt-3 pt-3 border-t border-slate-100">
        <div v-if="subLabel && subValue !== undefined" class="flex items-center justify-between text-xs">
          <span class="text-slate-400">{{ subLabel }}</span>
          <span class="font-medium text-slate-700">{{ subValue }}</span>
        </div>
        <p v-if="trendLabel" class="text-xs text-slate-400">{{ trendLabel }}</p>
      </div>
    </div>
  </div>
</template>
