import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

export function useLocale() {
  const { locale, availableLocales } = useI18n()

  const currentLocale = computed(() => locale.value)

  function setLocale(newLocale: string) {
    locale.value = newLocale
    localStorage.setItem('locale', newLocale)
  }

  function toggleLocale() {
    const currentIndex = availableLocales.indexOf(locale.value)
    const nextIndex = (currentIndex + 1) % availableLocales.length
    setLocale(availableLocales[nextIndex])
  }

  return {
    currentLocale,
    setLocale,
    toggleLocale,
    availableLocales,
  }
}
