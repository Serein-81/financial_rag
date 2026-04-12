<script setup lang="ts">
import { ref, onMounted } from 'vue'

const progress = ref(0)
const showProgress = ref(false)

onMounted(() => {
  showProgress.value = true
  const interval = setInterval(() => {
    if (progress.value < 90) {
      progress.value += Math.random() * 10
    }
  }, 200)

  setTimeout(() => {
    clearInterval(interval)
    progress.value = 100
  }, 1000)
})
</script>

<template>
  <div 
    v-if="showProgress"
    class="flex items-center justify-center h-full"
  >
    <div class="text-center">
      <div class="inline-block w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
      <p class="text-sm text-gray-500">加载中...</p>
    </div>
  </div>
</template>
