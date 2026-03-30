<script setup lang="ts">
import { useRoute } from 'vue-router'
import MainLayout from '@/components/MainLayout.vue'

const route = useRoute()

// 检查是否是登录或注册页面
const isAuthPage = () => {
  return route.name === 'login' || route.name === 'register'
}
</script>

<template>
  <!-- 如果是登录/注册页面，直接显示路由内容 -->
  <router-view v-if="isAuthPage()" />

  <!-- 否则显示主应用布局 -->
  <MainLayout v-else />
</template>
