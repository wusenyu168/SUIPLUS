<template>
  <v-card :loading="loading" class="sui-settings-card">
    <div class="sui-settings-toolbar">
      <v-tabs
        v-model="tab"
        color="primary"
        show-arrows
        class="sui-settings-tabs"
      >
        <v-tab value="t1" rounded="pill">{{ $t('setting.interface') }}</v-tab>
        <v-tab value="t2" rounded="pill">{{ $t('setting.sub') }}</v-tab>
        <v-tab value="t3" rounded="pill">{{ $t('setting.jsonSub') }}</v-tab>
        <v-tab value="t4" rounded="pill">{{ $t('setting.clashSub') }}</v-tab>
        <v-tab value="t5" rounded="pill">附加功能</v-tab>
      </v-tabs>
      <div class="sui-settings-actions">
        <v-btn color="primary" @click="save" :loading="loading" :disabled="!stateChange">
          {{ $t('actions.save') }}
        </v-btn>
        <v-btn variant="outlined" color="warning" @click="restartApp" :loading="loading" :disabled="stateChange">
          {{ $t('actions.restartApp') }}
        </v-btn>
      </div>
    </div>
    <v-card-text>
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
          <!-- ① 隧道与域名 -->
          <v-card variant="outlined" class="sui-block mb-4" rounded="lg">
            <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2 text-subtitle-1 font-weight-bold">
              <span>隧道与域名</span>
              <v-chip size="small" color="primary" variant="tonal">Argo / DDNS / 证书</v-chip>
            </v-card-title>
            <v-card-text>
              <v-alert type="info" variant="tonal" density="compact" class="mb-3">
                先在「界面」填写本机域名并保存；再开启优选。优选/Argo 与 DDNS 已分离。节点域名固定 DNS-only（灰云）。重建 Argo 会换新 SNI，客户端需重新订阅优选。
              </v-alert>
              <v-row class="mb-1">
                <v-col cols="12" sm="6" md="4">
                  <v-switch color="primary" v-model="suiplusPreferEnable" label="Argo默认+优选" hide-details />
                </v-col>
                <v-col cols="12" sm="6" md="4">
                  <v-switch color="primary" v-model="cfDdnsEnable" label="Cloudflare DDNS" hide-details />
                </v-col>
                <v-col cols="12" sm="6" md="4">
                  <v-switch color="primary" v-model="argoAutoRebuild" label="Argo异常自动重建" hide-details />
                  <div class="text-caption text-medium-emphasis mt-1">默认关；挂了才强建，冷却 30 分钟</div>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" md="4">
                  <v-text-field
                    v-model="settings.cfDdnsInterval"
                    label="DDNS 刷新间隔（秒）"
                    hint="仅刷新面板域名解析，不影响优选 SNI"
                    persistent-hint
                    type="number"
                    min="60"
                  ></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model="settings.cfDdnsToken" label="CF API Token" hide-details type="password"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model="settings.cfDdnsZone" label="Zone（主域名）" hide-details></v-text-field>
                </v-col>
              </v-row>
              <v-row align="end">
                <v-col cols="12" md="3">
                  <v-text-field v-model="settings.cfDdnsRecord" label="记录名（如 node 或 @）" hide-details></v-text-field>
                </v-col>
                <v-col cols="12" sm="6" md="3">
                  <v-btn color="primary" variant="tonal" block height="40" @click="issueCert" :loading="certLoading" :disabled="certLoading">
                    一键申请证书并绑定
                  </v-btn>
                </v-col>
                <v-col cols="12" sm="6" md="3">
                  <v-btn color="success" variant="tonal" block height="40" @click="copyPanelLink" :disabled="!certReady">
                    复制面板链接
                  </v-btn>
                </v-col>
                <v-col cols="12" sm="6" md="3">
                  <v-btn color="warning" variant="tonal" block height="40" @click="argoRebuild" :loading="argoLoading" :disabled="argoLoading || !suiplusPreferEnable">
                    立即重建 Argo
                  </v-btn>
                </v-col>
              </v-row>
              <div class="text-caption text-medium-emphasis mt-2" v-if="settings.argoDomain || settings.argoLastRebuildAt">
                <span v-if="settings.argoDomain">当前 Argo：{{ settings.argoDomain }}</span>
                <span v-if="settings.argoLastRebuildAt">　上次重建：{{ settings.argoLastRebuildAt }}</span>
              </div>
            </v-card-text>
          </v-card>

          <!-- ② 动态拨号 -->
          <v-card variant="outlined" class="sui-block" rounded="lg">
            <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2 text-subtitle-1 font-weight-bold">
              <span>动态拨号</span>
              <v-chip size="small" color="primary" variant="tonal">服务商线路 · 非面板域名</v-chip>
            </v-card-title>
            <v-card-text>
              <v-alert type="info" variant="tonal" density="compact" class="mb-3">
                换线断网正常；恢复后自动或点「获取 IP」。同 IP 重复获取不重开 72h。仅重拨成功后按钮灰 5 分钟。定时按勾选星期 + 时刻（面板时区）。重拨只刷 DDNS，不重建 Argo。
              </v-alert>
              <v-row class="mb-1">
                <v-col cols="12" sm="6" md="4">
                  <v-switch color="primary" v-model="pppoeEnable" label="动态拨号" hide-details />
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" md="4">
                  <v-text-field
                    v-model="settings.pppoeProviderDomain"
                    label="关联域名（服务商域名）"
                    hint="非本 SUI 面板域名"
                    persistent-hint
                  ></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model="settings.pppoeAccountId" label="账号 ID" hide-details></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model="settings.pppoePassword" label="密码" hide-details type="password"></v-text-field>
                </v-col>
              </v-row>

              <v-sheet class="sui-time-group pa-3 mb-3" rounded="lg">
                <v-row align="end">
                  <v-col cols="12" md="4">
                    <v-switch color="primary" v-model="pppoeScheduleEnable" label="定时自动重拨" hide-details />
                    <div class="text-caption mt-1" :class="pppoeScheduleEnable && scheduleNextLeft > 0 ? 'text-warning' : 'text-medium-emphasis'">
                      <template v-if="!pppoeScheduleEnable">未启用</template>
                      <template v-else-if="pppoeWeekdaySelected.length === 0">请勾选星期</template>
                      <template v-else-if="scheduleNextLeft > 0">距下次重拨 {{ scheduleNextText }}</template>
                      <template v-else>已到窗口 · 等待执行</template>
                    </div>
                  </v-col>
                  <v-col cols="12" sm="5" md="4">
                    <v-select
                      v-model="pppoeWeekdaySelected"
                      :items="weekdayOptions"
                      item-title="title"
                      item-value="value"
                      label="星期（可多选）"
                      multiple
                      chips
                      closable-chips
                      hide-details
                      density="comfortable"
                    ></v-select>
                  </v-col>
                  <v-col cols="12" sm="7" md="4">
                    <div class="text-caption text-medium-emphasis mb-1">时刻（时 / 分）</div>
                    <div class="sui-time-pair">
                      <v-select v-model="pppoeScheduleHour" :items="hourOptions" hide-details density="comfortable"></v-select>
                      <div class="sui-time-colon">:</div>
                      <v-select v-model="pppoeScheduleMinute" :items="minuteOptions" hide-details density="comfortable"></v-select>
                    </div>
                  </v-col>
                </v-row>
              </v-sheet>

              <v-sheet class="sui-ip-panel pa-3 mb-3" rounded="lg">
                <v-row dense>
                  <v-col cols="12" sm="4">
                    <div class="text-caption text-medium-emphasis">上次 IP</div>
                    <div class="text-body-1 font-weight-medium">{{ settings.pppoePrevIp || '—' }}</div>
                  </v-col>
                  <v-col cols="12" sm="4">
                    <div class="text-caption text-medium-emphasis">本次 IP</div>
                    <div class="text-body-1 font-weight-bold">{{ settings.pppoeLastIp || '—' }}</div>
                  </v-col>
                  <v-col cols="12" sm="4">
                    <div class="text-caption text-medium-emphasis">冷却 / 状态</div>
                    <div class="text-body-2" :class="(sessionLeft > 0 || cooldownLeft > 0) ? 'text-warning' : 'text-medium-emphasis'">
                      <template v-if="sessionLeft > 0">会话剩余 {{ sessionText }}</template>
                      <template v-else-if="settings.pppoePending === 'true'">待确认 · 自动/手动获取 IP</template>
                      <template v-else-if="!settings.pppoeLastAt">可立即重拨</template>
                      <div v-if="cooldownLeft > 0" class="text-caption mt-1" :class="sessionLeft > 0 ? 'text-medium-emphasis' : 'text-warning'">
                        可再拨 {{ cooldownText }}
                      </div>
                      <div v-if="settings.pppoeLastAt" class="text-caption text-medium-emphasis mt-1">
                        上次获取 {{ settings.pppoeLastAt }}
                      </div>
                    </div>
                  </v-col>
                </v-row>
              </v-sheet>

              <div class="d-flex flex-wrap align-center ga-3">
                <v-btn color="warning" variant="tonal" @click="pppoeRedial" :loading="pppoeLoading" :disabled="pppoeLoading || cooldownLeft > 0">
                  立即重拨
                </v-btn>
                <v-btn color="primary" variant="tonal" @click="pppoeShowIp" :loading="pppoeShowLoading" :disabled="pppoeShowLoading || !pppoeEnable">
                  获取 IP
                </v-btn>
              </div>
            </v-card-text>
          </v-card>

          <v-alert class="mt-4" type="info" variant="tonal" density="compact">
            记录名只填主机名；动态拨号请先保存。重建 Argo 后请重新订阅优选节点。
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
import { Ref, computed, inject, onMounted, onUnmounted, ref } from 'vue'
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
  argoAutoRebuild: "false",
  argoRebuildCooldownSec: "1800",
  argoLastRebuildTs: "",
  argoLastRebuildAt: "",
  argoDomain: "",
  pppoeEnable: "false",
  pppoeProviderDomain: "",
  pppoeAccountId: "",
  pppoePassword: "",
  pppoeScheduleEnable: "false",
  pppoeScheduleDays: "1",
  pppoeScheduleWeekdays: "1,2,3,4,5,6,7",
  pppoeScheduleTime: "03:00",
  pppoeLastIp: "",
  pppoePrevIp: "",
  pppoeLastAt: "",
  pppoeLastSuccessTs: "",
  pppoeSessionStartTs: "",
  pppoeCooldownUntilTs: "",
  pppoeLastAutoFireDate: "",
  pppoePending: "false",
})
const certLoading = ref(false)
const pppoeLoading = ref(false)
const pppoeShowLoading = ref(false)
const argoLoading = ref(false)
const nowTick = ref(Date.now())
let cooldownTimer: ReturnType<typeof setInterval> | null = null
const SESSION_SEC = 72 * 3600

const applyPppoeFields = (obj: Record<string, string>) => {
  if (!obj) return
  for (const k of ['pppoePrevIp', 'pppoeLastIp', 'pppoeLastAt', 'pppoeLastSuccessTs', 'pppoeSessionStartTs', 'pppoeCooldownUntilTs', 'pppoePending', 'argoDomain', 'argoLastRebuildTs', 'argoLastRebuildAt'] as const) {
    if (obj[k] != null && obj[k] !== '') (settings.value as any)[k] = obj[k]
  }
  if (obj.pppoePending === 'true' || obj.pppoePending === 'false') settings.value.pppoePending = obj.pppoePending
  oldSettings.value = { ...settings.value }
}

const pad2 = (n: number) => n.toString().padStart(2, '0')
const hourOptions = Array.from({ length: 24 }, (_, i) => pad2(i))
const minuteOptions = Array.from({ length: 60 }, (_, i) => pad2(i))
const weekdayOptions = [
  { title: '星期一', value: 1 },
  { title: '星期二', value: 2 },
  { title: '星期三', value: 3 },
  { title: '星期四', value: 4 },
  { title: '星期五', value: 5 },
  { title: '星期六', value: 6 },
  { title: '星期日', value: 7 },
]

const parseWeekdays = (raw: string | undefined): number[] => {
  const text = (raw || '').trim()
  if (!text) return []
  const out: number[] = []
  for (const part of text.split(/[,;]/)) {
    const n = parseInt(part.trim(), 10)
    if (n >= 1 && n <= 7 && !out.includes(n)) out.push(n)
  }
  return out.sort((a, b) => a - b)
}

const pppoeWeekdaySelected = computed({
  get: () => parseWeekdays(settings.value.pppoeScheduleWeekdays),
  set: (vals: number[]) => {
    const uniq = [...new Set((vals || []).map((n) => Number(n)).filter((n) => n >= 1 && n <= 7))].sort((a, b) => a - b)
    settings.value.pppoeScheduleWeekdays = uniq.join(',')
  }
})

const parseScheduleParts = () => {
  const raw = (settings.value.pppoeScheduleTime || '03:00').trim()
  const m = raw.match(/^(\d{1,2}):(\d{1,2})$/)
  if (!m) return { h: '03', mi: '00' }
  const h = Math.min(23, Math.max(0, parseInt(m[1], 10)))
  const mi = Math.min(59, Math.max(0, parseInt(m[2], 10)))
  return { h: pad2(h), mi: pad2(mi) }
}

const pppoeScheduleHour = computed({
  get: () => parseScheduleParts().h,
  set: (h: string) => {
    const mi = parseScheduleParts().mi
    settings.value.pppoeScheduleTime = `${h}:${mi}`
  }
})

const pppoeScheduleMinute = computed({
  get: () => parseScheduleParts().mi,
  set: (mi: string) => {
    const h = parseScheduleParts().h
    settings.value.pppoeScheduleTime = `${h}:${mi}`
  }
})

/** Panel-TZ wall clock parts (ISO weekday Mon=1..Sun=7). */
const tzParts = (timeZone: string, at: Date = new Date()) => {
  const tz = (timeZone || 'Asia/Shanghai').trim() || 'Asia/Shanghai'
  try {
    const fmt = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      weekday: 'short',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    })
    const parts = Object.fromEntries(fmt.formatToParts(at).filter((p) => p.type !== 'literal').map((p) => [p.type, p.value]))
    const wdMap: Record<string, number> = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7 }
    const isoWeekday = wdMap[parts.weekday] || 1
    return {
      tz,
      isoWeekday,
      year: parseInt(parts.year, 10),
      month: parseInt(parts.month, 10),
      day: parseInt(parts.day, 10),
      hour: parseInt(parts.hour, 10),
      minute: parseInt(parts.minute, 10),
      second: parseInt(parts.second, 10),
      dateStr: `${parts.year}-${parts.month}-${parts.day}`,
    }
  } catch {
    const d = at
    const iso = d.getDay() === 0 ? 7 : d.getDay()
    return {
      tz: 'Asia/Shanghai',
      isoWeekday: iso,
      year: d.getFullYear(),
      month: d.getMonth() + 1,
      day: d.getDate(),
      hour: d.getHours(),
      minute: d.getMinutes(),
      second: d.getSeconds(),
      dateStr: `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`,
    }
  }
}

/** Approx epoch ms for a wall-clock datetime in panel TZ (works for Asia/* fixed offsets). */
const wallToUtcMs = (p: { year: number; month: number; day: number; hour: number; minute: number; second?: number }, timeZone: string) => {
  const guess = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second || 0)
  const seen = tzParts(timeZone, new Date(guess))
  const asUtc = Date.UTC(seen.year, seen.month - 1, seen.day, seen.hour, seen.minute, seen.second)
  const target = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second || 0)
  return guess + (target - asUtc)
}

const addDaysYmd = (y: number, m: number, d: number, add: number) => {
  const dt = new Date(Date.UTC(y, m - 1, d + add))
  return { year: dt.getUTCFullYear(), month: dt.getUTCMonth() + 1, day: dt.getUTCDate() }
}

const formatHms = (total: number) => {
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const r = total % 60
  return `${h}:${m.toString().padStart(2, '0')}:${r.toString().padStart(2, '0')}`
}

/** Next scheduled fire ms, or 0 if none / already in today's window awaiting timer. */
const scheduleNextFireMs = computed(() => {
  void nowTick.value
  if (!pppoeScheduleEnable.value) return 0
  const selected = pppoeWeekdaySelected.value
  if (!selected.length) return 0
  const { h, mi } = parseScheduleParts()
  const hh = parseInt(h, 10)
  const mm = parseInt(mi, 10)
  const tz = (settings.value.timeLocation || 'Asia/Shanghai').trim() || 'Asia/Shanghai'
  const now = new Date()
  const cur = tzParts(tz, now)
  const lastFire = (settings.value.pppoeLastAutoFireDate || '').trim()
  const set = new Set(selected)

  for (let offset = 0; offset <= 8; offset++) {
    const ymd = addDaysYmd(cur.year, cur.month, cur.day, offset)
    // weekday of that YMD in tz ≈ use noon UTC of that calendar day adjusted
    const noonMs = wallToUtcMs({ ...ymd, hour: 12, minute: 0, second: 0 }, tz)
    const wd = tzParts(tz, new Date(noonMs)).isoWeekday
    if (!set.has(wd)) continue
    const fireMs = wallToUtcMs({ ...ymd, hour: hh, minute: mm, second: 0 }, tz)
    const dateStr = `${ymd.year}-${pad2(ymd.month)}-${pad2(ymd.day)}`
    if (offset === 0) {
      if (lastFire === cur.dateStr) continue // already ran today
      if (fireMs <= now.getTime()) {
        // in/after today's window and not yet recorded → show 0 (awaiting timer)
        return 0
      }
    }
    if (fireMs > now.getTime()) return fireMs
  }
  return 0
})

const scheduleNextLeft = computed(() => {
  void nowTick.value
  const ms = scheduleNextFireMs.value
  if (!ms) return 0
  const left = Math.floor((ms - Date.now()) / 1000)
  return left > 0 ? left : 0
})

const scheduleNextText = computed(() => formatHms(scheduleNextLeft.value))

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
  cooldownTimer = setInterval(() => { nowTick.value = Date.now() }, 1000)
})

onUnmounted(() => {
  if (cooldownTimer) clearInterval(cooldownTimer)
  cooldownTimer = null
})

const parseTs = (raw: string | undefined) => {
  const t = (raw || '').trim()
  if (!t) return 0
  const n = parseInt(t, 10)
  return n || 0
}

const sessionStartTs = () => {
  const s = parseTs(settings.value.pppoeSessionStartTs)
  if (s) return s
  // migrate older field
  return parseTs(settings.value.pppoeLastSuccessTs)
}

const cooldownLeft = computed(() => {
  void nowTick.value
  const until = parseTs(settings.value.pppoeCooldownUntilTs)
  if (!until) return 0
  const left = until - Math.floor(Date.now() / 1000)
  return left > 0 ? left : 0
})

const sessionLeft = computed(() => {
  void nowTick.value
  const ts = sessionStartTs()
  if (!ts) return 0
  const left = SESSION_SEC - (Math.floor(Date.now() / 1000) - ts)
  return left > 0 ? left : 0
})

const cooldownText = computed(() => {
  const s = cooldownLeft.value
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${r.toString().padStart(2, '0')}`
})

const sessionText = computed(() => formatHms(sessionLeft.value))

const loadData = async () => {
  loading.value = true
  const msg = await HttpUtils.get('api/settings')
  loading.value = false
  if (msg.success) {
    setData(msg.obj)
    // migrate empty weekdays once for old installs
    if (!(settings.value.pppoeScheduleWeekdays || '').trim()) {
      settings.value.pppoeScheduleWeekdays = '1,2,3,4,5,6,7'
    }
    // #region agent log
    const tz = (settings.value.timeLocation || 'Asia/Shanghai').trim()
    const cur = tzParts(tz)
    const left = scheduleNextLeft.value
    const fireMs = scheduleNextFireMs.value
    fetch('http://127.0.0.1:7611/ingest/dfd3c41e-3d1d-41b7-b746-566bc0e53a83',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'0bfd89'},body:JSON.stringify({sessionId:'0bfd89',runId:'weekday-sched',hypothesisId:'H2',location:'Settings.vue:loadData',message:'schedule next countdown',data:{timeLocation:tz,panelNow:cur,weekdays:settings.value.pppoeScheduleWeekdays||'',scheduleTime:settings.value.pppoeScheduleTime||'',scheduleEnable:settings.value.pppoeScheduleEnable||'',lastAutoFire:settings.value.pppoeLastAutoFireDate||'',nextFireMs:fireMs,nextFireIso:fireMs?new Date(fireMs).toISOString():null,scheduleNextLeft:left,scheduleNextText:left?formatHms(left):''},timestamp:Date.now()})}).catch(()=>{})
    // #endregion
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

const argoAutoRebuild = computed({
  get: () => { return settings.value.argoAutoRebuild == "true" },
  set: (v:boolean) => { settings.value.argoAutoRebuild = v ? "true" : "false" }
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
  if (pppoeLoading.value || cooldownLeft.value > 0) return
  await HttpUtils.post('api/save', { object: 'settings', action: 'set', data: JSON.stringify(settings.value) })
  pppoeLoading.value = true
  const msg = await HttpUtils.post('api/pppoeRedial', {})
  const obj = (msg.obj || {}) as Record<string, string>
  applyPppoeFields(obj)
  if (msg.success) {
    push.success({
      title: i18n.global.t('success'),
      duration: 8000,
      message: obj.message || msg.msg || `重拨完成 ${obj.pppoePrevIp || ''} → ${obj.pppoeLastIp || ''}`
    })
    await loadData()
  } else {
    // Network drop / pending: keep any prev IP from obj; tip to 获取 IP
    if (obj.pppoePrevIp || obj.pppoePending === 'true') applyPppoeFields(obj)
    push.error({
      title: i18n.global.t('error'),
      duration: 12000,
      message: (msg.msg || '').replace(/^pppoeRedial:\s*/i, '') || '重拨失败；若已断网，恢复后请点「获取 IP」'
    })
  }
  pppoeLoading.value = false
}

const pppoeShowIp = async () => {
  if (pppoeShowLoading.value || !pppoeEnable.value) return
  await HttpUtils.post('api/save', { object: 'settings', action: 'set', data: JSON.stringify(settings.value) })
  pppoeShowLoading.value = true
  const msg = await HttpUtils.post('api/pppoeShowIp', {})
  const obj = (msg.obj || {}) as Record<string, string>
  applyPppoeFields(obj)
  if (msg.success) {
    push.success({
      title: i18n.global.t('success'),
      duration: 6000,
      message: obj.message || msg.msg || '已获取 IP'
    })
    await loadData()
  } else {
    push.error({
      title: i18n.global.t('error'),
      duration: 10000,
      message: (msg.msg || '').replace(/^pppoeShowIp:\s*/i, '') || '获取 IP 失败'
    })
  }
  pppoeShowLoading.value = false
}

const argoRebuild = async () => {
  if (argoLoading.value || !suiplusPreferEnable.value) return
  await HttpUtils.post('api/save', { object: 'settings', action: 'set', data: JSON.stringify(settings.value) })
  argoLoading.value = true
  const msg = await HttpUtils.post('api/argoRebuild', {})
  const obj = (msg.obj || {}) as Record<string, string>
  applyPppoeFields(obj)
  if (msg.success) {
    push.success({
      title: i18n.global.t('success'),
      duration: 10000,
      message: obj.message || msg.msg || 'Argo 已重建，请重新订阅优选节点'
    })
    await loadData()
  } else {
    push.error({
      title: i18n.global.t('error'),
      duration: 12000,
      message: (msg.msg || '').replace(/^argoRebuild:\s*/i, '') || 'Argo 重建失败'
    })
  }
  argoLoading.value = false
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

<style scoped>
.sui-settings-card {
  border: 1px solid #e5e9f2;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06) !important;
}
.sui-settings-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px 4px;
  border-bottom: 1px solid #eef2f7;
}
.sui-settings-tabs {
  flex: 1 1 auto;
  min-width: 240px;
}
.sui-settings-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.sui-block {
  background: #fff;
  border-color: #e5e9f2 !important;
}
.sui-time-group {
  background: #f8fafc;
  border: 1px dashed #dbe3ef !important;
}
.sui-time-pair {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 8px;
  align-items: center;
}
.sui-time-colon {
  font-weight: 700;
  color: #64748b;
  text-align: center;
}
.sui-ip-panel {
  background: #f8fafc;
  border: 1px solid #e5e9f2;
}
@media (max-width: 600px) {
  .sui-settings-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .sui-settings-actions {
    justify-content: center;
  }
}
</style>
