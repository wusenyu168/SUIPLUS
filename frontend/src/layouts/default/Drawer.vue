<template>
  <v-navigation-drawer
    v-model="showDrawer"
    :temporary="isMobile"
    :expand-on-hover="!isMobile"
    :rail="!isMobile"
    :permanent="!isMobile"
    class="sui-drawer"
    @click="isMobile ? $emit('toggleDrawer') : null"
  >
    <v-list-item
      height="63"
      class="sui-brand"
      title="SUIPLUS"
      subtitle="S-UI Panel"
    >
      <template v-slot:prepend>
        <div class="sui-logo">S</div>
      </template>
      <template v-slot:append v-if="isMobile">
        <v-icon icon="mdi-close" />
      </template>
    </v-list-item>

    <v-divider class="border-opacity-25"></v-divider>

    <v-list density="compact" nav class="sui-nav">
      <v-list-item link
        v-for="item in menu"
        :key="item.title"
        :to="item.path"
        :active="router.currentRoute.value.path == item.path"
        rounded="lg"
        class="sui-nav-item">
        <template v-slot:prepend>
          <v-icon :icon="item.icon"></v-icon>
        </template>
        <v-list-item-title v-text="$t(item.title)"></v-list-item-title>
      </v-list-item>
    </v-list>
    <template v-slot:append>
      <v-list-item prepend-icon="mdi-logout" :title="$t('menu.logout')" class="sui-nav-item" @click="Logout"></v-list-item>
    </template>
  </v-navigation-drawer>
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import router from '@/router'
import { logout } from '@/plugins/httputil'

const props = defineProps(['isMobile','displayDrawer'])

const showDrawer = computed((): boolean => {
  return props.displayDrawer
})

const menu = [
  { title: 'pages.home', icon: 'mdi-home',  path: '/' },
  { title: 'pages.inbounds', icon: 'mdi-cloud-download',  path: '/inbounds' },
  { title: 'pages.clients', icon: 'mdi-account-multiple',  path: '/clients' },
  { title: 'pages.outbounds', icon: 'mdi-cloud-upload',  path: '/outbounds' },
  { title: 'pages.endpoints', icon: 'mdi-cloud-tags',  path: '/endpoints' },
  { title: 'pages.services', icon: 'mdi-server',  path: '/services' },
  { title: 'pages.tls', icon: 'mdi-certificate',  path: '/tls' },
  { title: 'pages.basics', icon: 'mdi-application-cog',  path: '/basics' },
  { title: 'pages.rules', icon: 'mdi-routes',  path: '/rules' },
  { title: 'pages.dns', icon: 'mdi-dns',  path: '/dns' },
  { title: 'pages.admins', icon: 'mdi-account-tie',  path: '/admins' },
  { title: 'pages.settings', icon: 'mdi-cog',  path: '/settings' },
]

const Logout = async () => {
  logout()
}
</script>

<style scoped>
.sui-drawer {
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
  color: #e2e8f0;
}
.sui-brand :deep(.v-list-item-title) {
  font-weight: 700;
  letter-spacing: 0.3px;
  color: #fff !important;
}
.sui-brand :deep(.v-list-item-subtitle) {
  color: #94a3b8 !important;
  opacity: 1;
}
.sui-logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-weight: 800;
  color: #fff;
  font-size: 14px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.35);
  margin-inline-end: 8px;
}
.sui-nav-item {
  color: #cbd5e1 !important;
  margin: 2px 4px;
}
.sui-nav-item :deep(.v-icon) {
  color: #94a3b8;
}
.sui-nav-item.v-list-item--active {
  background: rgba(37, 99, 235, 0.22) !important;
  color: #fff !important;
}
.sui-nav-item.v-list-item--active :deep(.v-icon) {
  color: #93c5fd;
}
.sui-nav-item:hover {
  background: rgba(255, 255, 255, 0.05) !important;
}
</style>
