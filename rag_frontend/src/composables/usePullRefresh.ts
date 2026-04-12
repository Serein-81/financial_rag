import { ref, onMounted, onUnmounted } from 'vue'

interface UsePullRefreshOptions {
  onRefresh: () => Promise<void>
  threshold?: number
  maxPullDistance?: number
}

export function usePullRefresh(options: UsePullRefreshOptions) {
  const { onRefresh, threshold = 80, maxPullDistance = 120 } = options

  const isPulling = ref(false)
  const pullDistance = ref(0)
  const isRefreshing = ref(false)
  const touchStartY = ref(0)
  const isAtTop = ref(true)

  const checkScrollTop = () => {
    const scrollTop = window.scrollY || document.documentElement.scrollTop
    isAtTop.value = scrollTop < 10
  }

  const handleTouchStart = (e: TouchEvent) => {
    if (!isAtTop.value || isRefreshing.value) return
    touchStartY.value = e.touches[0].clientY
    isPulling.value = true
  }

  const handleTouchMove = (e: TouchEvent) => {
    if (!isPulling.value || !isAtTop.value) return

    const currentY = e.touches[0].clientY
    const diff = currentY - touchStartY.value

    if (diff > 0) {
      e.preventDefault()
      pullDistance.value = Math.min(diff * 0.5, maxPullDistance)
    }
  }

  const handleTouchEnd = async () => {
    if (!isPulling.value) return

    if (pullDistance.value >= threshold) {
      isRefreshing.value = true
      try {
        await onRefresh()
      } catch (error) {
        console.error('Refresh failed:', error)
      } finally {
        isRefreshing.value = false
      }
    }

    isPulling.value = false
    pullDistance.value = 0
  }

  const handleScroll = () => {
    checkScrollTop()
  }

  onMounted(() => {
    window.addEventListener('scroll', handleScroll, { passive: true })
    document.addEventListener('touchstart', handleTouchStart, { passive: true })
    document.addEventListener('touchmove', handleTouchMove, { passive: false })
    document.addEventListener('touchend', handleTouchEnd, { passive: true })
  })

  onUnmounted(() => {
    window.removeEventListener('scroll', handleScroll)
    document.removeEventListener('touchstart', handleTouchStart)
    document.removeEventListener('touchmove', handleTouchMove)
    document.removeEventListener('touchend', handleTouchEnd)
  })

  return {
    pullDistance,
    isRefreshing,
    isPulling,
  }
}
