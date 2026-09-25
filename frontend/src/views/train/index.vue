<template>
  <section class="page" data-module="train">
    <header class="page-head">
      <div>
        <h2>培训演练管理</h2>
        <p class="page-desc">按岗位与设备类型排期培训，签到后进入演练，考核成绩逐人录入；状态沿 待开班→培训中→待考核→已结业 流转，不可回退。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="toggleCreate">登记培训班次</button>
        <button class="btn" type="button" @click="toggleGraduates">结业名单</button>
        <button class="btn" type="button" @click="exportRows">导出培训清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>培训编号</span>
        <input v-model="filters.keyword" placeholder="按培训编号检索" />
      </label>
      <label class="filter-item">
        <span>培训岗位</span>
        <input v-model="filters.position" placeholder="按培训岗位检索" />
      </label>
      <label class="filter-item">
        <span>设备类型</span>
        <select v-model="filters.device">
          <option value="">全部设备</option>
          <option v-for="device in deviceTypes" :key="device" :value="device">{{ device }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>培训状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="showCreate" class="panel">
      <h3 class="panel-title">登记培训班次（按岗位与设备类型排期）</h3>
      <form class="form-grid" @submit.prevent="submitCreate">
        <label class="form-item">
          <span>培训岗位</span>
          <input v-model="createForm.培训岗位" placeholder="如：信号机检修岗" />
        </label>
        <label class="form-item">
          <span>设备类型</span>
          <select v-model="createForm.设备类型">
            <option value="">请选择</option>
            <option v-for="device in deviceTypes" :key="device" :value="device">{{ device }}</option>
          </select>
        </label>
        <label class="form-item">
          <span>计划开班日期</span>
          <input v-model="createForm.计划开班日期" type="date" />
        </label>
        <label class="form-item">
          <span>培训讲师</span>
          <input v-model="createForm.培训讲师" placeholder="授课师傅" />
        </label>
        <label class="form-item">
          <span>演练项目</span>
          <input v-model="createForm.演练项目" placeholder="如：信号机机构拆装" />
        </label>
        <label class="form-item">
          <span>学员名单（顿号或逗号分隔）</span>
          <input v-model="createForm.学员名单" placeholder="如：李新、周凯、陈晨" />
        </label>
        <label class="form-item">
          <span>合格线（留空按 60 分）</span>
          <input v-model="createForm.合格线" type="number" min="0" max="100" />
        </label>
        <button class="btn primary" type="submit">提交排期</button>
        <button class="btn ghost" type="button" @click="toggleCreate">取消</button>
      </form>
    </div>

    <div v-if="showGraduates" class="panel">
      <h3 class="panel-title">结业名单（仅已结业班次的合格学员）</h3>
      <table class="data-table">
        <thead>
          <tr><th>培训编号</th><th>培训岗位</th><th>设备类型</th><th>演练项目</th><th>结业时间</th><th>结业学员</th><th>未通过学员</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in graduates" :key="item.培训编号">
            <td>{{ item.培训编号 }}</td>
            <td>{{ item.培训岗位 }}</td>
            <td>{{ item.设备类型 }}</td>
            <td>{{ item.演练项目 }}</td>
            <td>{{ item.结业时间 ?? '—' }}</td>
            <td><span v-for="name in item.结业学员" :key="name" class="tag">{{ name }}</span></td>
            <td>{{ item.未通过学员.length ? item.未通过学员.join('、') : '—' }}</td>
          </tr>
          <tr v-if="!graduates.length">
            <td colspan="7" class="empty-state">暂无结业记录</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="scoreEntry" class="panel">
      <h3 class="panel-title">录入考核成绩：{{ scoreEntry.培训编号 }} · {{ scoreEntry.演练项目 }}（合格线 {{ scoreEntry.合格线 }} 分）</h3>
      <div v-for="person in scoreEntry.participants ?? []" :key="person.姓名" class="score-row">
        <span class="name">{{ person.姓名 }}</span>
        <span class="meta">{{ person.签到 ? `已签到 ${person.签到时间 ?? ''}` : '未签到' }}</span>
        <template v-if="person.考核结论">
          <span class="meta">已录入：{{ person.成绩 }} 分，{{ person.考核结论 }}（{{ person.成绩录入人 }} · {{ person.成绩录入时间 }}）</span>
        </template>
        <template v-else>
          <input v-model="scoreInputs[person.姓名]" type="number" min="0" max="100" placeholder="考核成绩" />
        </template>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="submitScores">提交成绩</button>
        <button class="btn ghost" type="button" @click="closeScores">收起</button>
      </div>
      <ul v-if="scoreResults.length" class="result-list">
        <li v-for="result in scoreResults" :key="result.trainee" :class="result.ok ? 'ok-text' : 'error-text'">
          {{ result.message }}
        </li>
      </ul>
      <ul v-if="(scoreEntry.日志 ?? []).length" class="log-list">
        <li v-for="(log, index) in scoreEntry.日志" :key="index">
          {{ log.时间 }} · {{ log.操作人 }} · {{ log.动作 }}：{{ log.说明 }}
        </li>
      </ul>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="openScores(row)">录入成绩</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无培训演练数据，可先登记培训班次</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条培训演练记录</span>
      <span v-if="message" :class="messageOk ? 'ok-text' : 'error-text'">{{ message }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

interface Participant {
  姓名: string
  签到: boolean
  签到时间: string | null
  成绩: number | null
  考核结论: string | null
  成绩录入人: string | null
  成绩录入时间: string | null
}

interface LogEntry {
  时间: string
  操作人: string
  动作: string
  说明: string
}

interface TrainRow {
  id: number
  status: string
  培训编号: string
  培训岗位: string
  设备类型: string
  计划开班日期: string
  培训讲师: string
  演练项目: string
  合格线: number
  学员人数: number
  培训状态: string
  participants?: Participant[]
  日志?: LogEntry[]
  [key: string]: unknown
}

interface GraduateItem {
  培训编号: string
  培训岗位: string
  设备类型: string
  培训讲师: string
  演练项目: string
  结业时间: string | null
  结业学员: string[]
  未通过学员: string[]
}

interface ScoreResult {
  trainee: string
  ok: boolean
  message: string
}

const store = useSessionStore()

const ENDPOINT = '/api/train'
const columns = ["培训编号", "培训岗位", "设备类型", "计划开班日期", "培训讲师", "演练项目", "学员人数", "培训状态"]
const actions = ["开班签到", "结束演练", "确认结业"]
const statuses = ["待开班", "培训中", "待考核", "已结业"]
const deviceTypes = ["信号机", "转辙机", "轨道电路", "联锁设备", "列车防护"]

const rows = ref<TrainRow[]>([])
const total = ref(0)
const message = ref('')
const messageOk = ref(false)
const filters = ref({ keyword: '', position: '', device: '', status: '' })
const stats = ref(statuses.map((label) => ({ label, value: 0 })))

const showCreate = ref(false)
const createForm = ref({ 培训岗位: '', 设备类型: '', 计划开班日期: '', 培训讲师: '', 演练项目: '', 学员名单: '', 合格线: '' })

const showGraduates = ref(false)
const graduates = ref<GraduateItem[]>([])

const scoreEntry = ref<TrainRow | null>(null)
const scoreInputs = ref<Record<string, string>>({})
const scoreResults = ref<ScoreResult[]>([])

function note(text: string, ok: boolean) {
  message.value = text
  messageOk.value = ok
}

function resetFilters() {
  filters.value = { keyword: '', position: '', device: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function toggleCreate() {
  showCreate.value = !showCreate.value
}

async function toggleGraduates() {
  showGraduates.value = !showGraduates.value
  if (showGraduates.value) {
    try {
      const payload = await fetchJson<{ items: GraduateItem[] }>(`${ENDPOINT}/graduates`)
      graduates.value = payload.items ?? []
    } catch (error) {
      note(error instanceof Error ? error.message : '结业名单读取失败', false)
    }
  }
}

async function submitCreate() {
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm.value, 操作人: store.operator } }),
    })
    const payload = await response.json()
    note(payload.message ?? '培训班次登记结果未知', Boolean(payload.ok))
    if (payload.ok) {
      showCreate.value = false
      createForm.value = { 培训岗位: '', 设备类型: '', 计划开班日期: '', 培训讲师: '', 演练项目: '', 学员名单: '', 合格线: '' }
      await reload()
    }
  } catch (error) {
    note(error instanceof Error ? error.message : '培训班次登记失败', false)
  }
}

async function runAction(action: string, row: TrainRow) {
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action, 操作人: store.operator } }),
    })
    const payload = await response.json()
    note(payload.message ?? '培训演练动作结果未知', Boolean(payload.ok))
    await reload()
  } catch (error) {
    note(error instanceof Error ? error.message : '培训演练操作失败', false)
  }
}

async function openScores(row: TrainRow) {
  scoreResults.value = []
  try {
    const detail = await fetchJson<TrainRow>(`${ENDPOINT}/${row.id}`)
    scoreEntry.value = detail
    const inputs: Record<string, string> = {}
    for (const person of detail.participants ?? []) {
      if (!person.考核结论) {
        inputs[person.姓名] = ''
      }
    }
    scoreInputs.value = inputs
  } catch (error) {
    note(error instanceof Error ? error.message : '培训明细读取失败', false)
  }
}

function closeScores() {
  scoreEntry.value = null
  scoreResults.value = []
}

async function submitScores() {
  if (!scoreEntry.value) {
    return
  }
  const items = (scoreEntry.value.participants ?? [])
    .filter((person) => !person.考核结论)
    .map((person) => ({ 学员: person.姓名, 成绩: scoreInputs.value[person.姓名] ?? '' }))
  try {
    const response = await request(`${ENDPOINT}/${scoreEntry.value.id}/scores`, {
      method: 'POST',
      body: JSON.stringify({ values: { 成绩列表: items, 操作人: store.operator } }),
    })
    const payload = await response.json()
    scoreResults.value = payload.results ?? []
    note(payload.message ?? '成绩录入结果未知', Boolean(payload.ok))
    scoreEntry.value = await fetchJson<TrainRow>(`${ENDPOINT}/${scoreEntry.value.id}`)
    await reload()
  } catch (error) {
    note(error instanceof Error ? error.message : '成绩录入失败', false)
  }
}

async function refreshStats() {
  try {
    const payload = await fetchJson<{ counts: Record<string, number> }>(`${ENDPOINT}/stats`)
    stats.value = stats.value.map((item) => ({ ...item, value: payload.counts[item.label] ?? 0 }))
  } catch {
    // 统计卡片刷新失败不阻断列表展示
  }
}

async function reload() {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(filters.value)) {
    if (value) {
      query.set(key, value)
    }
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('培训演练列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await refreshStats()
  } catch (error) {
    note(error instanceof Error ? error.message : '培训演练列表读取失败', false)
  }
}

onMounted(reload)
</script>
