<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import MainLayout from '@/components/MainLayout.vue'
import AsyncRouteLoading from '@/components/AsyncRouteLoading.vue'
import { useEnterpriseTheme } from '@/composables/useEnterpriseTheme'

const route = useRoute()

useEnterpriseTheme()

const isAuthPage = computed(() => {
  return route.name === 'login' || route.name === 'register'
})
</script>

<template>
  <!-- 如果是登录/注册页面，直接显示路由内容 -->
  <router-view v-if="isAuthPage" />

  <!-- 否则显示主应用布局 -->
  <MainLayout v-else />
</template>
