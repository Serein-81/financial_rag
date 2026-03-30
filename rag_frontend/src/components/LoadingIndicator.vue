<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const phases = [
  'chat.loading.scanning',
  'chat.loading.querying',
  'chat.loading.generating',
]

const currentPhase = ref(0)
let interval: number

onMounted(() => {
  interval = window.setInterval(() => {
    currentPhase.value = (currentPhase.value + 1) % phases.length
  }, 800)
})

onUnmounted(() => {
  clearInterval(interval)
})
</script>

<template>
  <div class="flex items-center gap-3 p-4">
    <!-- Animated Cursor -->
    <span class="inline-block w-4 h-8 bg-blue-600 animate-blink font-mono text-blue-600">▋</span>

    <!-- Loading Text -->
    <span class="font-mono text-sm text-slate-500">
      {{ t(phases[currentPhase]) }}
    </span>
  </div>
</template>
