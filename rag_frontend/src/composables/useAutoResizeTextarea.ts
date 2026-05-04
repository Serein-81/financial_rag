import { nextTick, onMounted, ref, watch, type Ref } from 'vue'

interface AutoResizeTextareaOptions {
  minHeight?: number
  maxHeight?: number
}

export function useAutoResizeTextarea(
  value: Ref<string>,
  options: AutoResizeTextareaOptions = {}
) {
  const textareaRef = ref<HTMLTextAreaElement | null>(null)
  const minHeight = options.minHeight ?? 44
  const maxHeight = options.maxHeight ?? 148

  function resizeTextarea() {
    const textarea = textareaRef.value
    if (!textarea) return

    textarea.style.height = 'auto'
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight)
    textarea.style.height = `${nextHeight}px`
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
  }

  function resetTextarea() {
    nextTick(resizeTextarea)
  }

  watch(value, () => {
    resetTextarea()
  }, { flush: 'post' })

  onMounted(resetTextarea)

  return {
    textareaRef,
    resizeTextarea,
    resetTextarea,
  }
}
