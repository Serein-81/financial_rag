<script setup lang="ts">
import { computed } from 'vue'
import { X, CheckCircle, AlertCircle, Loader2 } from 'lucide-vue-next'

interface Props {
  visible: boolean
  progress: number
  status: 'idle' | 'preparing' | 'exporting' | 'completed' | 'failed'
  message: string
  estimatedTime?: number | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

const progressPercentage = computed(() => Math.round(props.progress))

const statusConfig = computed(() => {
  switch (props.status) {
    case 'preparing':
      return {
        icon: Loader2,
        color: 'text-blue-600',
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-200'
      }
    case 'exporting':
      return {
        icon: Loader2,
        color: 'text-emerald-600',
        bgColor: 'bg-emerald-50',
        borderColor: 'border-emerald-200'
      }
    case 'completed':
      return {
        icon: CheckCircle,
        color: 'text-emerald-600',
        bgColor: 'bg-emerald-50',
        borderColor: 'border-emerald-200'
      }
    case 'failed':
      return {
        icon: AlertCircle,
        color: 'text-red-600',
        bgColor: 'bg-red-50',
        borderColor: 'border-red-200'
      }
    default:
      return {
        icon: Loader2,
        color: 'text-gray-600',
        bgColor: 'bg-gray-50',
        borderColor: 'border-gray-200'
      }
  }
})

const formattedTime = computed(() => {
  if (!props.estimatedTime) return null
  if (props.estimatedTime < 60) {
    return `约 ${props.estimatedTime} 秒`
  }
  const minutes = Math.floor(props.estimatedTime / 60)
  const seconds = props.estimatedTime % 60
  return `约 ${minutes} 分 ${seconds} 秒`
})

function handleClose() {
  if (props.status !== 'preparing' && props.status !== 'exporting') {
    emit('close')
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-300 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
        @click.self="handleClose"
      >
        <Transition
          enter-active-class="transition duration-300 ease-out"
          enter-from-class="opacity-0 scale-95"
          enter-to-class="opacity-100 scale-100"
          leave-active-class="transition duration-200 ease-in"
          leave-from-class="opacity-100 scale-100"
          leave-to-class="opacity-0 scale-95"
        >
          <div
            v-if="visible"
            :class="[
              'w-full max-w-md bg-white rounded-2xl shadow-2xl border-2',
              statusConfig.borderColor
            ]"
          >
            <div class="p-6">
              <div class="flex items-center justify-between mb-6">
                <div class="flex items-center gap-3">
                  <div
                    :class="[
                      'w-12 h-12 rounded-xl flex items-center justify-center',
                      statusConfig.bgColor
                    ]"
                  >
                    <component
                      :is="statusConfig.icon"
                      :size="24"
                      :class="[
                        statusConfig.color,
                        (status === 'preparing' || status === 'exporting') && 'animate-spin'
                      ]"
                    />
                  </div>
                  <div>
                    <h3 class="text-lg font-semibold text-gray-900">导出文件</h3>
                    <p :class="['text-sm', statusConfig.color]">{{ message }}</p>
                  </div>
                </div>

                <button
                  v-if="status !== 'preparing' && status !== 'exporting'"
                  @click="emit('close')"
                  class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <X :size="20" class="text-gray-500" />
                </button>
              </div>

              <div class="mb-4">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-sm font-medium text-gray-700">导出进度</span>
                  <span class="text-sm font-semibold" :class="statusConfig.color">
                    {{ progressPercentage }}%
                  </span>
                </div>

                <div class="h-3 bg-gray-100 rounded-full overflow-hidden">
                  <Transition
                    enter-active-class="transition-all duration-300 ease-out"
                    enter-from-class="w-0"
                    leave-active-class="transition-all duration-200 ease-in"
                    leave-to-class="w-0"
                  >
                    <div
                      :class="[
                        'h-full rounded-full transition-all duration-300',
                        status === 'failed' ? 'bg-red-500' :
                        status === 'completed' ? 'bg-emerald-500' : 'bg-gradient-to-r from-emerald-500 to-green-500'
                      ]"
                      :style="{ width: `${progressPercentage}%` }"
                    />
                  </Transition>
                </div>

                <div
                  v-if="formattedTime && status === 'exporting'"
                  class="flex items-center justify-between mt-2"
                >
                  <span class="text-xs text-gray-500">预计剩余时间</span>
                  <span class="text-xs font-medium text-gray-700">{{ formattedTime }}</span>
                </div>
              </div>

              <div
                v-if="status === 'completed'"
                class="flex items-center justify-center gap-2 py-2 bg-emerald-50 rounded-lg"
              >
                <CheckCircle :size="16" class="text-emerald-600" />
                <span class="text-sm font-medium text-emerald-700">文件导出成功！</span>
              </div>

              <div
                v-if="status === 'failed'"
                class="flex items-center justify-center gap-2 py-2 bg-red-50 rounded-lg"
              >
                <AlertCircle :size="16" class="text-red-600" />
                <span class="text-sm font-medium text-red-700">导出失败，请重试</span>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
