import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/ModernLoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/ModernRegisterView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    name: 'chat',
    component: () => import('@/views/ModernChatView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/search',
    name: 'search',
    component: () => import('@/views/ModernSearchView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/documents',
    name: 'documents',
    component: () => import('@/views/ModernDocumentsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('@/views/KnowledgeManagementView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/knowledge/:id',
    name: 'knowledge-detail',
    component: () => import('@/views/ModernKnowledgeDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/sessions',
    name: 'sessions',
    component: () => import('@/views/SessionsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/knowledge-graph',
    name: 'knowledge-graph',
    component: () => import('@/views/KnowledgeGraphView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/enterprise',
    name: 'enterprise',
    component: () => import('@/views/EnterpriseView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/logs',
    name: 'logs',
    component: () => import('@/views/LogsView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/chat-logs',
    name: 'chat-logs',
    component: () => import('@/views/ChatLogsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/ModernProfileView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/audit/upload',
    name: 'audit-upload',
    component: () => import('@/views/AuditUploadView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/audit/result/:id',
    name: 'audit-result',
    component: () => import('@/views/AuditResultView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/tax-submission',
    name: 'tax-submission',
    component: () => import('@/views/TaxSubmissionView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/group-chat',
    name: 'group-chat',
    component: () => import('@/views/GroupChatView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/analytics',
    name: 'analytics',
    component: () => import('@/views/AnalyticsDashboard.vue'),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard for authentication
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    // Redirect to login if trying to access protected route
    next('/login')
  } else if ((to.name === 'login' || to.name === 'register') && authStore.isLoggedIn) {
    // Redirect to chat if already logged in
    next('/')
  } else {
    next()
  }
})

export default router
