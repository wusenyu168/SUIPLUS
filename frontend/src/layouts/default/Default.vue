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
</style>