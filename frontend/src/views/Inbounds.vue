<template>
  <InboundVue 
    v-model="modal.visible"
    :visible="modal.visible"
    :id="modal.id"
    :inTags="inTags"
    :tlsConfigs="tlsConfigs"
    @close="closeModal"
  />
  <Stats
    v-model="stats.visible"
    :visible="stats.visible"
    :resource="stats.resource"
    :tag="stats.tag"
    @close="closeStats"
  />
  <v-row>
    <v-col cols="12" class="d-flex justify-center">
      <v-btn color="primary" @click="showModal(0)">{{ $t('actions.add') }}</v-btn>
    </v-col>
  </v-row>
  <v-row align="stretch">
    <v-col cols="12" sm="6" md="4" lg="3" v-for="(item, index) in <any[]>inbounds" :key="item.tag">
      <v-card class="sui-entity-card" rounded="lg" elevation="2" :title="item.tag">
        <v-card-subtitle>{{ item.type }}</v-card-subtitle>
        <v-card-text>
          <div class="sui-kv-row">
            <span class="k">{{ $t('in.addr') }}</span>
            <span class="v" :title="item.listen">{{ item.listen }}</span>
          </div>
          <div class="sui-kv-row" v-if="addrRemarks(item).length">
            <span class="k">订阅</span>
            <span class="v" :title="addrRemarks(item).join(' / ')">{{ addrRemarks(item).join(' / ') }}</span>
          </div>
          <div class="sui-kv-row">
            <span class="k">{{ $t('in.port') }}</span>
            <span class="v">{{ item.listen_port }}</span>
          </div>
          <div class="sui-kv-row">
            <span class="k">{{ $t('objects.tls') }}</span>
            <span class="v">{{ item.tls_id > 0 ? $t('enable') : $t('disable') }}</span>
          </div>
          <div class="sui-kv-row">
            <span class="k">{{ $t('pages.clients') }}</span>
            <span class="v">
              <template v-if="item.users">
                <v-tooltip activator="parent" dir="ltr" location="bottom" v-if="item.users.length > 0">
                  <span v-for="u in item.users">{{ u }}<br /></span>
                </v-tooltip>
                {{ item.users.length }}
              </template>
              <template v-else>-</template>
            </span>
          </div>
          <div class="sui-kv-row">
            <span class="k">{{ $t('online') }}</span>
            <span class="v">
              <template v-if="onlines.includes(item.tag)">
                <v-chip density="comfortable" size="small" color="success" variant="flat">{{ $t('online') }}</v-chip>
              </template>
              <template v-else>-</template>
            </span>
          </div>
        </v-card-text>
        <v-divider></v-divider>
        <v-card-actions>
          <v-btn icon="mdi-file-edit" @click="showModal(item.id)">
            <v-icon />
            <v-tooltip activator="parent" location="top" :text="$t('actions.edit')"></v-tooltip>
          </v-btn>
          <v-btn icon="mdi-file-remove" style="margin-inline-start:0;" color="warning" @click="delOverlay[index] = true">
            <v-icon />
            <v-tooltip activator="parent" location="top" :text="$t('actions.del')"></v-tooltip>
          </v-btn>
          <v-overlay
            v-model="delOverlay[index]"
            contained
            class="align-center justify-center"
          >
            <v-card :title="$t('actions.del')" rounded="lg">
              <v-divider></v-divider>
              <v-card-text>{{ $t('confirm') }}</v-card-text>
              <v-card-actions>
                <v-btn color="error" variant="outlined" @click="delInbound(item.id)">{{ $t('yes') }}</v-btn>
                <v-btn color="success" variant="outlined" @click="delOverlay[index] = false">{{ $t('no') }}</v-btn>
              </v-card-actions>
            </v-card>
          </v-overlay>
          <v-btn icon="mdi-content-duplicate" :loading="cloneLoading" @click="clone(item.id)">
            <v-icon />
            <v-tooltip activator="parent" location="top" :text="$t('actions.clone')"></v-tooltip>
          </v-btn>
          <v-btn icon="mdi-chart-line" @click="showStats(item.tag)" v-if="Data().enableTraffic">
            <v-icon />
            <v-tooltip activator="parent" location="top" :text="$t('stats.graphTitle')"></v-tooltip>
          </v-btn>
        </v-card-actions>
      </v-card>      
    </v-col>
  </v-row>
</template>

<script lang="ts" setup>
import Data from '@/store/modules/data'
import InboundVue from '@/layouts/modals/Inbound.vue'
import Stats from '@/layouts/modals/Stats.vue'
import { Config } from '@/types/config'
import { computed, ref } from 'vue'
import { createInbound, Inbound } from '@/types/inbounds'
import RandomUtil from '@/plugins/randomUtil'

const appConfig = computed((): Config => {
  return <Config> Data().config
})

const inbounds = computed((): Inbound[] => {
  return <Inbound[]> Data().inbounds
})

const tlsConfigs = computed((): any[] => {
  return <any[]> Data().tlsConfigs
})

const inTags = computed((): string[] => {
  return [...inbounds.value?.map(i => i.tag), ...Data().endpoints?.filter((e:any) => e.listen_port > 0).map((e:any) => e.tag)]
})

const onlines = computed(() => {
  return Data().onlines.inbound?? []
})

const addrRemarks = (item: any): string[] => {
  let addrs = item?.addrs
  if (typeof addrs === 'string') {
    try { addrs = JSON.parse(addrs) } catch { return [] }
  }
  if (!Array.isArray(addrs) || addrs.length === 0) return []
  return addrs.map((a: any) => {
    const r = String(a?.remark || '').replace(/^-/, '')
    const s = String(a?.server || '')
    if (r && s) return `${r}→${s}`
    return r || s
  }).filter(Boolean)
}

const modal = ref({
  visible: false,
  id: 0,
})

let delOverlay = ref(new Array<boolean>)

const showModal = (id: number) => {
  modal.value.id = id
  modal.value.visible = true
}
const closeModal = () => {
  modal.value.visible = false
}

const delInbound = async (id: number) => {
  const index = inbounds.value.findIndex(i => i.id == id)
  const tag = inbounds.value[index].tag

  const success = await Data().save("inbounds", "del", tag)
  if (success) delOverlay.value[index] = false
}

let cloneLoading = ref(false)

const clone = async (id: number) => {
  cloneLoading.value = true
  const inboundArray = await Data().loadInbounds([id])
  const inbound = inboundArray[0]
  let newTag = inbound.type + "-" + RandomUtil.randomSeq(3)
  const newInbound = createInbound(inbound.type, { ...inbound,
    id: 0,
    tag: newTag,
    listen_port: RandomUtil.randomIntRange(10000, 60000),
  })
  await Data().save("inbounds", "new", newInbound)
  cloneLoading.value = false
}

const stats = ref({
  visible: false,
  resource: "inbound",
  tag: "",
})

const showStats = (tag: string) => {
  stats.value.tag = tag
  stats.value.visible = true
}
const closeStats = () => {
  stats.value.visible = false
}
</script>
