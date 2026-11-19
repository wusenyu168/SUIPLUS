<template>
  <v-card :loading="loading">
    <v-tabs
    v-model="tab"
    color="primary"
    align-tabs="center"
    show-arrows
  >
    <v-tab value="t1">{{ $t('setting.interface') }}</v-tab>
    <v-tab value="t2">{{ $t('setting.sub') }}</v-tab>
    <v-tab value="t3">{{ $t('setting.jsonSub') }}</v-tab>
    <v-tab value="t4">{{ $t('setting.clashSub') }}</v-tab>
    <v-tab value="t5">附加功能</v-tab>
  </v-tabs>
  <v-card-text>
    <v-row align="center" justify="center" style="margin-bottom: 10px;">
      <v-col cols="auto">
        <v-btn color="primary" @click="save" :loading="loading" :disabled="!stateChange">
          {{ $t('actions.save') }}
        </v-btn>
      </v-col>
      <v-col cols="auto">
        <v-btn variant="outlined" color="warning" @click="restartApp" :loading="loading" :disabled="stateChange">
          {{ $t('actions.restartApp') }}
        </v-btn>
      </v-col>
    </v-row>
    <v-window v-model="tab">
      <v-window-item value="t1">
        <v-row>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.webListen" :label="$t('setting.addr')" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model.number="webPort" min="1" type="number" :label="$t('setting.port')" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.webPath" :label="$t('setting.webPath')" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.webDomain" :label="$t('setting.domain')" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.webKeyFile" :label="$t('setting.sslKey')" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.webCertFile" :label="$t('setting.sslCert')" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.webURI" :label="$t('setting.webUri')" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field
              type="number"
              v-model.number="sessionMaxAge"
              min="0"
              :label="$t('setting.sessionAge')"
              :suffix="$t('date.m')"
              hide-details
              ></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field
              type="number"
              v-model.number="trafficAge"
              min="0"
              :label="$t('setting.trafficAge')"
              :suffix="$t('date.d')"
              hide-details
              ></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.timeLocation" :label="$t('setting.timeLoc')" hide-details></v-text-field>
          </v-col>
        </v-row>
      </v-window-item>

      <v-window-item value="t5">
        <v-row>
          <v-col cols="12">
            <v-alert type="info" variant="tonal" density="compact" class="mb-2">
              先在「界面」填写本机域名并保存；再开启优选。优选/Argo 与 DDNS 已分离。节点域名固定 DNS-only（灰云）。未绑域名时订阅仅公网 IP。
            </v-alert>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-switch color="primary" v-model="suiplusPreferEnable" label="Argo默认+优选" hide-details />
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-switch color="primary" v-model="cfDdnsEnable" label="Cloudflare DDNS" hide-details />
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field
              v-model="settings.cfDdnsInterval"
              label="DDNS 刷新间隔(秒，默认300=5分钟)"
              hint="仅刷新面板域名解析，不影响优选 SNI"
              persistent-hint
              type="number"
              min="60"
            ></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.cfDdnsToken" label="CF API Token" hide-details type="password"></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.cfDdnsZone" label="Zone（主域名，勿预填）" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.cfDdnsRecord" label="记录名（如 node 或 @）" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-btn color="primary" variant="tonal" @click="issueCert" :loading="certLoading" :disabled="certLoading">
              一键申请证书并绑定
            </v-btn>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-btn
              color="success"
              variant="tonal"
              @click="copyPanelLink"
              :disabled="!certReady"
            >
              复制面板链接
            </v-btn>
          </v-col>
        </v-row>

        <v-divider class="my-4"></v-divider>
        <v-row>
          <v-col cols="12">
            <v-alert type="info" variant="tonal" density="compact" class="mb-2">
              动态拨号：关联域名填 VPS 服务商域名（不是本面板域名）。满 N 天未换 IP 则在设定时刻自动重拨；手动可随时重拨，成功后 5 分钟冷却。成功后刷新 CF DDNS，不重建优选 SNI。
            </v-alert>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-switch color="primary" v-model="pppoeEnable" label="动态拨号" hide-details />
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field
              v-model="settings.pppoeProviderDomain"
              label="关联域名（服务商域名）"
              hint="非本 SUI 面板域名"
              persistent-hint
            ></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.pppoeAccountId" label="账号 ID" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.pppoePassword" label="密码" hide-details type="password"></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-switch color="primary" v-model="pppoeScheduleEnable" label="定时自动重拨" hide-details />
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field
              v-model="settings.pppoeScheduleDays"
              label="周期（天，任意 N）"
              type="number"
              min="1"
              hint="满 N 天未换 IP 才自动重拨"
              persistent-hint
            ></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field
              v-model="settings.pppoeScheduleTime"
              label="时刻 HH:MM"
              placeholder="03:00"
              hint="固定时刻，如 03:00"
              persistent-hint
            ></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-btn color="warning" variant="tonal" @click="pppoeRedial" :loading="pppoeLoading" :disabled="pppoeLoading">
              立即重拨
            </v-btn>
          </v-col>
          <v-col cols="12" sm="6" md="4" class="d-flex align-center">
            <div class="text-medium-emphasis text-body-2">
              上次 IP：{{ settings.pppoePrevIp || '—' }}　本次 IP：{{ settings.pppoeLastIp || '—' }}
              <template v-if="settings.pppoeLastAt"><br />时间：{{ settings.pppoeLastAt }}</template>
            </div>
          </v-col>
        </v-row>

        <v-alert class="mt-4" type="info" variant="tonal" density="compact">
          记录名只填主机名（如 node），Zone 填主域。节点域名固定灰云。动态拨号请先保存；手动成功后 5 分钟内不可再拨。
        </v-alert>
      </v-window-item>

      <v-window-item value="t2">
        <v-row>
          <v-col cols="12" sm="6" md="4">
            <v-switch color="primary" v-model="subEncode" :label="$t('setting.subEncode')" hide-details />
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-switch color="primary" v-model="subShowInfo" :label="$t('setting.subInfo')" hide-details />
          </v-col>
        </v-row>
        <v-row>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.subListen" :label="$t('setting.addr')" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field
              type="number"
              v-model.number="subPort"
              min="1"
              :label="$t('setting.port')"
              hide-details></v-text-field>
          </v-col>
        </v-row>
        <v-row>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.subKeyFile" :label="$t('setting.sslKey')" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.subCertFile" :label="$t('setting.sslCert')" hide-details></v-text-field>
          </v-col>
        </v-row>
        <v-row>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.subDomain" :label="$t('setting.domain')" hide-details></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.subPath" :label="$t('setting.path')" hide-details></v-text-field>
          </v-col>
        </v-row>
        <v-row>
          <v-col cols="12" sm="6" md="4">
            <v-text-field
              type="number"
              v-model.number="subUpdates"
              min="0"
              :label="$t('setting.update')"
              hide-details
              ></v-text-field>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-text-field v-model="settings.subURI" :label="$t('setting.subUri')" hide-details></v-text-field>
          </v-col>
        </v-row>
      </v-window-item>

      <v-window-item value="t3">
        <SubJsonExtVue :settings="settings" />
      </v-window-item>

      <v-window-item value="t4">
        <SubClashExtVue :settings="settings" />
      </v-window-item>
    </v-window>
  </v-card-text>
</v-card>
</template>

<script lang="ts" setup>
import { i18n } from '@/locales'
import { Ref, computed, inject, onMounted, ref } from 'vue'
import HttpUtils from '@/plugins/httputil'
import { FindDiff } from '@/plugins/utils'
import SubJsonExtVue from '@/components/SubJsonExt.vue'
import SubClashExtVue from '@/components/SubClashExt.vue'
import { push } from 'notivue'
const tab = ref("t1")
const loading:Ref = inject('loading')?? ref(false)
const oldSettings = ref({})

const settings = ref({
	webListen: "",
	webDomain: "",
	webPort: "2095",
	webCertFile: "",
	webKeyFile: "",
  webPath: "/app/",
  webURI: "",
	sessionMaxAge: "0",
  trafficAge: "30",
	timeLocation: "Asia/Shanghai",
  subListen: "",
	subPort: "2096",
	subPath: "/sub/",
	subDomain: "",
	subCertFile: "",
	subKeyFile: "",
	subUpdates: "12",
	subEncode: "true",
	subShowInfo: "false",
	subURI: "",
  subJsonExt: "",
  subClashExt: "",
  cfDdnsEnable: "false",
  cfDdnsToken: "",
  cfDdnsZone: "",
  cfDdnsRecord: "",
  cfDdnsInterval: "300",
  cfDdnsProxied: "false",
  suiplusPreferEnable: "false",
  pppoeEnable: "false",
  pppoeProviderDomain: "",
  pppoeAccountId: "",
  pppoePassword: "",
  pppoeScheduleEnable: "false",
  pppoeScheduleDays: "1",
  pppoeScheduleTime: "03:00",
  pppoeLastIp: "",
  pppoePrevIp: "",
  pppoeLastAt: "",
  pppoeLastSuccessTs: "",
  pppoeLastAutoFireDate: "",
})
const certLoading = ref(false)
const pppoeLoading = ref(false)

/** 证书已绑定：域名 + 证书/密钥路径齐全后，才允许复制面板链接 */
const certReady = computed(() => {
  const ready = !!(
    settings.value.webDomain &&
    settings.value.webDomain.trim() &&
    settings.value.webCertFile &&
    settings.value.webCertFile.trim() &&
    settings.value.webKeyFile &&
    settings.value.webKeyFile.trim()
  )
  return ready
})

const panelLink = computed(() => {
  const host = (settings.value.webDomain || '').trim()
  if (!host) return ''
  const isTLS = !!(settings.value.webCertFile || settings.value.webKeyFile)
  let path = settings.value.webPath || '/app/'
  if (!path.startsWith('/')) path = '/' + path
  if (!path.endsWith('/')) path += '/'
  let port = (settings.value.webPort || '2095').toString()
  const protocol = isTLS ? 'https:' : 'http:'
  if ((isTLS && port === '443') || (!isTLS && port === '80')) {
    port = ''
  } else {
    port = `:${port}`
  }
  return `${protocol}//${host}${port}${path}`
})

onMounted(async () => {
  loading.value = true
  await loadData()
  loading.value = false
})

const loadData = async () => {
  loading.value = true
  const msg = await HttpUtils.get('api/settings')
  loading.value = false
  if (msg.success) {
    setData(msg.obj)
  }
}

const setData = (data: any) => {
  settings.value = data
  oldSettings.value = { ...data }
}

const save = async () => {
  loading.value = true
  const msg = await HttpUtils.post('api/save', { object: 'settings', action: 'set', data: JSON.stringify(settings.value) })
  if (msg.success) {
    push.success({
      title: i18n.global.t('success'),
      duration: 5000,
      message: i18n.global.t('actions.set') + " " + i18n.global.t('pages.settings')
    })
    setData(msg.obj.settings)
  }
  loading.value = false
}

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

const restartApp = async () => {
  loading.value = true
  const msg = await HttpUtils.post('api/restartApp',{})
  if (msg.success) {
    let url = settings.value.webURI
    if (url !== "") {
      const isTLS = settings.value.webCertFile !== "" || settings.value.webKeyFile !== ""
      url = buildURL(settings.value.webDomain,settings.value.webPort.toString(),isTLS, settings.value.webPath)
    }
    await sleep(3000)
    window.location.replace(url)
  }
  loading.value = false
}

const buildURL = (host: string, port: string, isTLS: boolean, path: string) => {
  if (!host || host.length == 0) host = window.location.hostname
  if (!port || port.length == 0) port = window.location.port

  const protocol = isTLS ? "https:" : "http:"

  if (port === "" || (isTLS && port === "443") || (!isTLS && port === "80")) {
      port = ""
  } else {
      port = `:${port}`
  }

  return `${protocol}//${host}${port}${path}settings`
}

const subEncode = computed({
  get: () => { return settings.value.subEncode == "true" },
  set: (v:boolean) => { settings.value.subEncode = v ? "true" : "false" }
})

const subShowInfo = computed({
  get: () => { return settings.value.subShowInfo == "true" },
  set: (v:boolean) => { settings.value.subShowInfo = v ? "true" : "false" }
})

const cfDdnsEnable = computed({
  get: () => { return settings.value.cfDdnsEnable == "true" },
  set: (v:boolean) => { settings.value.cfDdnsEnable = v ? "true" : "false" }
})

const suiplusPreferEnable = computed({
  get: () => { return settings.value.suiplusPreferEnable == "true" },
  set: (v:boolean) => { settings.value.suiplusPreferEnable = v ? "true" : "false" }
})

const pppoeEnable = computed({
  get: () => { return settings.value.pppoeEnable == "true" },
  set: (v:boolean) => { settings.value.pppoeEnable = v ? "true" : "false" }
})

const pppoeScheduleEnable = computed({
  get: () => { return settings.value.pppoeScheduleEnable == "true" },
  set: (v:boolean) => { settings.value.pppoeScheduleEnable = v ? "true" : "false" }
})

const copyPanelLink = async () => {
  if (!certReady.value || !panelLink.value) {
    push.error({ title: i18n.global.t('error'), duration: 4000, message: '请先成功申请并绑定证书' })
    return
  }
  try {
    await navigator.clipboard.writeText(panelLink.value)
    push.success({
      title: i18n.global.t('success'),
      duration: 5000,
      message: '已复制：' + panelLink.value
    })
  } catch {
    push.error({ title: i18n.global.t('error'), duration: 6000, message: '复制失败，请手动复制：' + panelLink.value })
  }
}

/** 从 Zone+记录名拼出面板域名（与脚本逻辑一致） */
const deriveDomainFromDdns = () => {
  const zone = (settings.value.cfDdnsZone || '').trim()
  const record = (settings.value.cfDdnsRecord || '').trim()
  if (!zone) return ''
  if (!record || record === '@') return zone.toLowerCase()
  if (record.includes('.')) return record.toLowerCase()
  return `${record}.${zone}`.toLowerCase()
}

const pppoeRedial = async () => {
  if (pppoeLoading.value) return
  // Persist credentials first
  await HttpUtils.post('api/save', { object: 'settings', action: 'set', data: JSON.stringify(settings.value) })
  pppoeLoading.value = true
  const msg = await HttpUtils.post('api/pppoeRedial', {})
  if (msg.success) {
    const obj = (msg.obj || {}) as Record<string, string>
    if (obj.pppoePrevIp != null) settings.value.pppoePrevIp = obj.pppoePrevIp
    if (obj.pppoeLastIp != null) settings.value.pppoeLastIp = obj.pppoeLastIp
    if (obj.pppoeLastAt != null) settings.value.pppoeLastAt = obj.pppoeLastAt
    oldSettings.value = { ...settings.value }
    push.success({
      title: i18n.global.t('success'),
      duration: 8000,
      message: obj.message || msg.msg || `重拨完成 ${obj.pppoePrevIp || ''} → ${obj.pppoeLastIp || ''}`
    })
    await loadData()
  } else {
    push.error({
      title: i18n.global.t('error'),
      duration: 10000,
      message: (msg.msg || '').replace(/^pppoeRedial:\s*/i, '') || '重拨失败'
    })
  }
  pppoeLoading.value = false
}

const issueCert = async () => {
  if (certLoading.value) return
  certLoading.value = true
  // 点击即自动填写：webDomain 空时用 Zone+记录名拼好再保存
  const beforeDomain = (settings.value.webDomain || '').trim()
  if (!beforeDomain) {
    const derived = deriveDomainFromDdns()
    if (derived) {
      settings.value.webDomain = derived
      settings.value.subDomain = derived
    }
  }
  // Persist current fields first so script can read Token/Zone/Record/webDomain
  await HttpUtils.post('api/save', { object: 'settings', action: 'set', data: JSON.stringify(settings.value) })
  const msg = await HttpUtils.post('api/issueCert', {})
  if (msg.success) {
    const filled = (msg.obj || {}) as Record<string, string>
    const applyFilled = () => {
      if (filled.webDomain) settings.value.webDomain = filled.webDomain
      if (filled.subDomain) settings.value.subDomain = filled.subDomain
      if (filled.webCertFile) settings.value.webCertFile = filled.webCertFile
      if (filled.webKeyFile) settings.value.webKeyFile = filled.webKeyFile
      if (filled.subCertFile) settings.value.subCertFile = filled.subCertFile
      if (filled.subKeyFile) settings.value.subKeyFile = filled.subKeyFile
    }
    applyFilled()
    oldSettings.value = { ...settings.value }
    push.success({
      title: i18n.global.t('success'),
      duration: 8000,
      message: `证书已绑定${filled.webDomain ? ' ' + filled.webDomain : ''}；「复制面板链接」已可用，请重启面板使 HTTPS 生效`
    })
    await loadData()
    applyFilled()
  } else {
    push.error({
      title: i18n.global.t('error'),
      duration: 10000,
      message: msg.msg || '证书申请失败'
    })
  }
  certLoading.value = false
}

const webPort = computed({
  get: () => { return settings.value.webPort.length>0 ? parseInt(settings.value.webPort) : 2095 },
  set: (v:number) => { settings.value.webPort = v>0 ? v.toString() : "2095" }
})

const sessionMaxAge = computed({
  get: () => { return settings.value.sessionMaxAge.length>0 ? parseInt(settings.value.sessionMaxAge) : 0 },
  set: (v:number) => { settings.value.sessionMaxAge = v>0 ? v.toString() : "0" }
})

const trafficAge = computed({
  get: () => { return settings.value.trafficAge.length>0 ? parseInt(settings.value.trafficAge) : 0 },
  set: (v:number) => { settings.value.trafficAge = v>0 ? v.toString() : "0" }
})

const subPort = computed({
  get: () => { return settings.value.subPort.length>0 ? parseInt(settings.value.subPort) : 2096 },
  set: (v:number) => { settings.value.subPort = v>0 ? v.toString() : "2096" }
})

const subUpdates = computed({
  get: () => { return settings.value.subUpdates.length>0 ? parseInt(settings.value.subUpdates) : 12 },
  set: (v:number) => { settings.value.subUpdates = v>0 ? v.toString() : "12" }
})

const stateChange = computed(() => {
  return !FindDiff.deepCompare(settings.value,oldSettings.value)
})
</script>
