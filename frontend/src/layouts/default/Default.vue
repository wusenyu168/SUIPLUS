<template>
  <v-app style="overflow: auto;">
    <drawer :isMobile="isMobile" :displayDrawer="displayDrawer" @toggleDrawer="toggleDrawer" />
    <default-bar :isMobile="isMobile" @toggleDrawer="toggleDrawer" />
    <default-view />
  </v-app>
</template>

<script lang="ts" setup>
import { computed, ref } from 'vue'
import DefaultBar from './AppBar.vue'
import Drawer from './Drawer.vue'
import DefaultView from './View.vue'
import { useDisplay } from 'vuetify'

const { smAndDown } = useDisplay()
const displayDrawer = ref(false)

const toggleDrawer = () => {
  displayDrawer.value = !displayDrawer.value
}

const isMobile = computed( ():boolean =>{
  displayDrawer.value = !smAndDown.value
  return smAndDown.value
})
</script>

<style>
.v-card-subtitle {
  text-align: center;
  border-bottom: 1px solid #e5e9f2;
  min-height: 20px;
}
.v-switch.v-input {
  padding-inline-start: .6rem;
}
.v-application {
  background:
    radial-gradient(900px 320px at 20% -10%, #dbeafe 0%, transparent 55%),
    radial-gradient(700px 280px at 100% 0%, #e0e7ff 0%, transparent 45%),
    #f4f6fb !important;
}
.v-theme--dark.v-application {
  background:
    radial-gradient(900px 320px at 20% -10%, rgba(37,99,235,.18) 0%, transparent 55%),
    #0f172a !important;
}

/* 实体卡片：等高、底部操作居中、长文本省略 */
.sui-entity-card {
  height: 100%;
  display: flex !important;
  flex-direction: column;
  border: 1px solid #e5e9f2 !important;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06) !important;
}
.sui-entity-card .v-card-title {
  font-size: 15px !important;
  font-weight: 700 !important;
  line-height: 1.3;
  padding-bottom: 0 !important;
}
.sui-entity-card .v-card-subtitle {
  text-align: start !important;
  border-bottom: 0 !important;
  opacity: 1 !important;
  color: #64748b !important;
  margin-top: 0 !important;
  padding-top: 2px !important;
}
.sui-entity-card .v-card-text {
  flex: 1 1 auto;
  padding-top: 8px !important;
}
.sui-entity-card .v-card-actions {
  justify-content: center !important;
  padding: 4px 8px !important;
  min-height: 48px;
  gap: 2px;
}
.sui-kv-row {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: 4px 10px;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
}
.sui-kv-row .k { color: #64748b; }
.sui-kv-row .v {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  direction: ltr;
  text-align: start;
}
</style>