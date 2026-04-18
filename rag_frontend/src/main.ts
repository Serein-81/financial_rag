import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import './style.css'
import 'element-plus/dist/index.css'
import i18n from './locales'
import router from './router'
import Vue3Toastify from 'vue3-toastify'
import 'vue3-toastify/dist/index.css'

console.log('🚀 Initializing RAG Terminal...')

const app = createApp(App)
const pinia = createPinia()
console.log('✅ Vue app created')

app.use(pinia)
console.log('✅ Pinia initialized')

app.use(ElementPlus)
console.log('✅ Element Plus initialized')

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
console.log('✅ Element Plus Icons registered')

app.use(i18n)
console.log('✅ Vue I18n initialized')

app.use(router)
console.log('✅ Vue Router initialized')

app.use(Vue3Toastify, {
  autoClose: 3000,
  theme: 'colored',
  position: 'top-right',
  pauseOnFocusLoss: false,
  pauseOnHover: false,
  draggable: true,
  closeOnClick: true,
  transition: 'slide'
})
console.log('✅ Vue3 Toastify initialized')

app.mount('#app')
console.log('✅ Vue app mounted to #app')
