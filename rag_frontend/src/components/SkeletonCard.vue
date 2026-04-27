<script setup lang="ts">
interface Props {
  lines?: number
  hasHeader?: boolean
  hasImage?: boolean
}

withDefaults(defineProps<Props>(), {
  lines: 3,
  hasHeader: true,
  hasImage: false
})
</script>

<template>
  <div class="bg-white rounded-2xl border border-slate-200/80 p-5 animate-pulse">
    <div v-if="hasHeader" class="flex items-center gap-3 mb-4">
      <div class="w-10 h-10 rounded-xl bg-slate-200" />
      <div class="flex-1">
        <div class="h-4 bg-slate-200 rounded-lg w-1/3 mb-2" />
        <div class="h-3 bg-slate-100 rounded-lg w-1/2" />
      </div>
    </div>
    <div v-if="hasImage" class="w-full h-32 bg-slate-100 rounded-xl mb-4" />
    <div class="space-y-2.5">
      <div
        v-for="i in lines"
        :key="i"
        class="h-3 bg-slate-100 rounded-lg"
        :style="{ width: `${85 - (i - 1) * 15}%` }"
      />
    </div>
    <div class="flex gap-2 mt-4">
      <div class="h-8 bg-slate-100 rounded-lg w-20" />
      <div class="h-8 bg-slate-100 rounded-lg w-20" />
    </div>
  </div>
</template>
