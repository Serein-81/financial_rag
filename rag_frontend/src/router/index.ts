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
    path: '/multi-agent',
    name: 'multi-agent-chat',
    component: () => import('@/views/MultiAgentChatView.vue'),
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
    path: '/audit',
    redirect: '/audit/upload',
    name: 'audit',
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
    path: '/tax-upload-debug',
    name: 'tax-upload-debug',
    component: () => import('@/views/TaxUploadDebug.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/group-chat',
    name: 'group-chat',
    component: () => import('@/views/GroupChatView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/policy',
    name: 'policy',
    component: () => import('@/views/PolicyListView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/policy/:id',
    name: 'policy-detail',
    component: () => import('@/views/PolicyDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/policy-search',
    name: 'policy-search',
    redirect: '/policy',
    meta: { requiresAuth: true },
  },
  {
    path: '/tax-intelligence',
    name: 'tax-intelligence',
    component: () => import('@/views/TaxIntelligenceView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/financial-health',
    name: 'financial-health',
    component: () => import('@/views/FinancialHealthView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/financial-data-entry',
    name: 'financial-data-entry',
    component: () => import('@/views/FinancialDataEntryView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/financial-data-list',
    name: 'financial-data-list',
    component: () => import('@/views/FinancialDataListView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/test-data-guide',
    name: 'test-data-guide',
    component: () => import('@/views/TestDataGuideView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/contract-review',
    name: 'contract-review',
    component: () => import('@/views/ContractReviewView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/policy-notifications',
    name: 'policy-notifications',
    component: () => import('@/views/PolicyNotificationView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/enterprise-match',
    name: 'enterprise-match',
    component: () => import('@/views/EnterpriseMatchView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/analytics',
    name: 'analytics',
    component: () => import('@/views/AnalyticsDashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/agent-center',
    name: 'agent-center',
    component: () => import('@/views/AgentCenterView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/custom-tools',
    name: 'custom-tools',
    component: () => import('@/views/CustomToolsView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/agent-monitor',
    redirect: '/agent-center',
    name: 'agent-monitor',
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/agent-trace',
    redirect: '/agent-center',
    name: 'agent-trace',
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/hitl-approval',
    name: 'hitl-approval',
    component: () => import('@/views/HITLApprovalView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/intent-debug',
    name: 'intent-debug',
    component: () => import('@/views/IntentClassifierDebugView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/security-audit',
    name: 'security-audit',
    component: () => import('@/views/SecurityAuditView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/knowledge-graph-editor',
    name: 'knowledge-graph-editor',
    component: () => import('@/views/KnowledgeGraphEditorView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/task-management',
    name: 'task-management',
    component: () => import('@/views/TaskManagementView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/notifications',
    name: 'notifications',
    component: () => import('@/views/NotificationCenterView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/animation-demo',
    name: 'animation-demo',
    component: () => import('@/views/AnimationDemoView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard for authentication
router.beforeEach((to, from, next) => {
  try {
    const authStore = useAuthStore()
    const isAdmin = authStore.isAdmin || localStorage.getItem('rag_user_role') === 'admin'

    if (to.meta.requiresAuth && !authStore.isLoggedIn) {
      next('/login')
    } else if ((to.name === 'login' || to.name === 'register') && authStore.isLoggedIn) {
      next('/')
    } else if (to.meta.requiresAdmin && !isAdmin) {
      next('/')
    } else {
      next()
    }
  } catch (error) {
    console.error('Navigation guard error:', error)
    next('/login')
  }
})

router.onError((error) => {
  console.error('Router error:', error)
})

export default router
