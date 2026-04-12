# Socket Hang Up 错误修复总结

## 问题描述

前端开发服务器出现大量 `socket hang up` 错误：

```
[vite] http proxy error: /api/v1/notifications/list?page_size=100
Error: socket hang up
[vite] http proxy error: /api/v1/tenant-settings/me
Error: socket hang up
```

## 根本原因

**NotificationBar** 组件在加载时就调用 `loadNotifications()` API，即使用户没有登录也会发起 API 请求，导致：

1. 未认证用户访问页面
2. API 返回 403 错误（Missing tenant context）
3. 前端收到错误后反复重试
4. 产生大量 "socket hang up" 错误

## 修复方案

在以下3个文件中添加了认证检查，确保只有在用户登录后才调用通知相关API：

### 1. NotificationBar.vue
```typescript
// 修改前
onMounted(() => {
  loadNotifications()
})

// 修改后
onMounted(() => {
  if (isAuthenticated()) {
    loadNotifications()
  }
})

// 修改前
watch(() => props.modelValue, (isOpen) => {
  if (isOpen)