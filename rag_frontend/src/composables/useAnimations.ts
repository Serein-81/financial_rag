/**
 * 动画工具模块
 * 提供统一的动画功能，支持平滑降级
 */

import { ref, onMounted, onBeforeUnmount } from 'vue'
import { gsap } from 'gsap'

/**
 * 检测用户是否偏好减少动画
 */
export const prefersReducedMotion = (): boolean => {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * 检测低性能设备
 */
export const isLowEndDevice = (): boolean => {
  if (typeof navigator === 'undefined') return false
  return (
    (navigator as any).hardwareConcurrency <= 2 ||
    (navigator as any).deviceMemory <= 2
  )
}

/**
 * 动画偏好 Hook
 */
export const useAnimationPreference = () => {
  const shouldAnimate = ref(!prefersReducedMotion() && !isLowEndDevice())
  
  let mediaQuery: MediaQueryList | null = null
  
  onMounted(() => {
    mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    
    const handleChange = (e: MediaQueryListEvent) => {
      shouldAnimate.value = !e.matches && !isLowEndDevice()
    }
    
    mediaQuery.addEventListener('change', handleChange)
  })
  
  onBeforeUnmount(() => {
    if (mediaQuery) {
      mediaQuery.removeEventListener('change', () => {})
    }
  })
  
  return { shouldAnimate }
}

/**
 * 安全的动画执行器
 * 动画失败不会影响业务逻辑
 */
export const safeAnimate = async (
  animationFn: () => void | Promise<void>
): Promise<void> => {
  if (!shouldAnimate()) return
  
  try {
    await animationFn()
  } catch (error) {
    console.warn('Animation failed:', error)
  }
}

/**
 * 全局动画启用状态
 */
const shouldAnimate = (): boolean => {
  return !prefersReducedMotion() && !isLowEndDevice()
}

/**
 * 聊天消息气泡动画
 */
export const animateMessageBubble = (
  element: HTMLElement,
  type: 'user' | 'ai',
  onComplete?: () => void
): gsap.core.Tween | null => {
  if (!shouldAnimate() || !element) return null
  
  const animation = type === 'user'
    ? { x: [-30, 0], opacity: [0, 1] }
    : { y: [20, 0], scale: [0.95, 1], opacity: [0, 1] }
  
  return gsap.fromTo(
    element,
    { ...animation, transformOrigin: 'center' },
    {
      duration: 0.4,
      ease: 'back.out(1.7)',
      onComplete
    }
  )
}

/**
 * 打字机效果
 */
export const typewriterEffect = async (
  element: HTMLElement,
  text: string,
  speed: number = 30
): Promise<void> => {
  if (!shouldAnimate()) {
    element.textContent = text
    return
  }
  
  element.textContent = ''
  
  for (let i = 0; i <= text.length; i++) {
    element.textContent = text.slice(0, i)
    await new Promise(resolve => setTimeout(resolve, speed))
  }
}

/**
 * 淡入效果
 */
export const fadeIn = (
  element: HTMLElement,
  duration: number = 0.3
): gsap.core.Tween | null => {
  if (!shouldAnimate() || !element) return null
  
  return gsap.fromTo(
    element,
    { opacity: 0 },
    { opacity: 1, duration, ease: 'power2.out' }
  )
}

/**
 * 滑入效果
 */
export const slideIn = (
  element: HTMLElement,
  direction: 'left' | 'right' | 'up' | 'down' = 'up',
  duration: number = 0.4
): gsap.core.Tween | null => {
  if (!shouldAnimate() || !element) return null
  
  const fromProps: Record<string, [number, number]> = {
    left: { x: [-50, 0] },
    right: { x: [50, 0] },
    up: { y: [30, 0] },
    down: { y: [-30, 0] }
  }
  
  return gsap.fromTo(
    element,
    { opacity: 0, ...Object.fromEntries(fromProps[direction]) },
    { opacity: 1, x: 0, y: 0, duration, ease: 'power3.out' }
  )
}

/**
 * 按钮点击涟漪效果
 */
export const rippleEffect = (
  element: HTMLElement,
  event: MouseEvent
): gsap.core.Tween | null => {
  if (!shouldAnimate() || !element) return null
  
  const rect = element.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  const ripple = document.createElement('span')
  ripple.style.cssText = `
    position: absolute;
    width: 0;
    height: 0;
    background: rgba(255, 255, 255, 0.4);
    border-radius: 50%;
    transform: scale(0);
    pointer-events: none;
    left: ${x}px;
    top: ${y}px;
  `
  
  element.style.position = 'relative'
  element.style.overflow = 'hidden'
  element.appendChild(ripple)
  
  const animation = gsap.to(ripple, {
    width: 200,
    height: 200,
    marginLeft: -100,
    marginTop: -100,
    opacity: [1, 0],
    scale: [0, 1],
    duration: 0.6,
    ease: 'power2.out',
    onComplete: () => ripple.remove()
  })
  
  return animation
}

/**
 * 数字滚动动画
 */
export const animateNumber = (
  element: HTMLElement,
  endValue: number,
  duration: number = 1.5,
  prefix: string = '',
  suffix: string = ''
): gsap.core.Tween | null => {
  if (!shouldAnimate() || !element) return null
  
  const obj = { value: 0 }
  
  return gsap.to(obj, {
    value: endValue,
    duration,
    ease: 'power2.out',
    onUpdate: () => {
      element.textContent = `${prefix}${Math.round(obj.value).toLocaleString()}${suffix}`
    }
  })
}

/**
 * 卡片批量入场动画
 */
export const staggerCards = (
  container: HTMLElement,
  selector: string = '[data-animate]',
  staggerDelay: number = 0.05
): gsap.core.Tween | null => {
  if (!shouldAnimate() || !container) return null
  
  const cards = container.querySelectorAll(selector)
  
  if (cards.length === 0) return null
  
  return gsap.fromTo(
    cards,
    { opacity: 0, y: 30 },
    {
      opacity: 1,
      y: 0,
      duration: 0.4,
      stagger: staggerDelay,
      ease: 'power2.out'
    }
  )
}

/**
 * 加载骨架屏闪烁效果
 */
export const skeletonPulse = (
  element: HTMLElement
): gsap.core.Tween | null => {
  if (!shouldAnimate() || !element) return null
  
  return gsap.to(element, {
    opacity: [0.6, 1, 0.6],
    duration: 1.5,
    repeat: -1,
    ease: 'sine.inOut'
  })
}

/**
 * 错误抖动效果
 */
export const shakeError = (
  element: HTMLElement,
  intensity: number = 10
): gsap.core.Tween | null => {
  if (!shouldAnimate() || !element) return null
  
  return gsap.to(element, {
    x: [0, -intensity, intensity, -intensity, intensity, 0],
    duration: 0.5,
    ease: 'power2.out'
  })
}

/**
 * 成功弹跳效果
 */
export const bounceSuccess = (
  element: HTMLElement
): gsap.core.Tween | null => {
  if (!shouldAnimate() || !element) return null
  
  return gsap.fromTo(
    element,
    { scale: [0.8, 1.2, 1] },
    { duration: 0.5, ease: 'back.out(2)' }
  )
}

/**
 * 工具函数：延迟执行
 */
export const sleep = (ms: number): Promise<void> => {
  return new Promise(resolve => setTimeout(resolve, ms))
}
