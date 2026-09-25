<template>
  <section class="page training-page">
    <header class="page-head">
      <div>
        <h2>培训演练管理</h2>
        <p class="page-desc">按岗位与设备类型排期，签到后进入演练，逐条录入考核成绩；操作人和每一步流转时间全程留痕。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">安排培训</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="tabs" role="tablist">
      <button :class="{ active: activeTab === 'trainings' }" type="button" @click="switchTab('trainings')">培训记录</button>
      <button :class="{ active: activeTab === 'graduates' }" type="button" @click="switchTab('graduates')">结业名单</button>
    </div>

    <form v-if="activeTab === 'trainings'" class="filter-bar" @submit.prevent="reloadTrainings">
      <label class="filter-item">
        <span>关键字</span>
        <input v-model="filters.keyword" placeholder="培训编号 / 名称 / 师傅" />
      </label>
      <label class="filter-item">
        <span>岗位</span>
        <input v-model="filters.post" placeholder="如：信号工" />
      </label>
      <label class="filter-item">
        <span>设备类型</span>
        <select v-model="filters.deviceType">
          <option value="">全部</option>
          <option>信号机</option>
          <option>转辙机</option>
          <option>轨道电路</option>
          <option>联锁设备</option>
        </select>
      </label>
      <label class="filter-item">
        <span>状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="status in statuses" :key="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <form v-else class="filter-bar" @submit.prevent="reloadGraduates">
      <label class="filter-item">
        <span>关键字</span>
        <input v-model="graduateFilters.keyword" placeholder="姓名 / 培训编号 / 培训名称" />
      </label>
      <label class="filter-item">
        <span>岗位</span>
        <input v-model="graduateFilters.post" placeholder="如：信号工" />
      </label>
      <label class="filter-item">
        <span>设备类型</span>
        <select v-model="graduateFilters.deviceType">
          <option value="">全部</option>
          <option>信号机</option>
          <option>转辙机</option>
          <option>轨道电路</option>
          <option>联锁设备</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetGraduateFilters">重置条件</button>
    </form>

    <table v-if="activeTab === 'trainings'" class="data-table">
      <thead>
        <tr>
          <th v-for="column in trainingColumns" :key="column">{{ column }}</th>
          <th>办理</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in trainings" :key="String(row.id)">
          <td v-for="column in trainingColumns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(Number(row.id))">
              {{ row.status === '待考核' ? '录入成绩' : '详情/办理' }}
            </button>
            <button v-if="row.status === '培训中'" class="link" type="button" @click="finishDrill(Number(row.id), true)">结束演练</button>
          </td>
        </tr>
        <tr v-if="!trainings.length">
          <td :colspan="trainingColumns.length + 1" class="empty-state">暂无符合条件的培训排期</td>
        </tr>
      </tbody>
    </table>

    <table v-else class="data-table">
      <thead>
        <tr>
          <th v-for="column in graduateColumns" :key="column">{{ column }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in graduates" :key="String(row.id)">
          <td v-for="column in graduateColumns" :key="column">{{ row[column] ?? '—' }}</td>
        </tr>
        <tr v-if="!graduates.length">
          <td :colspan="graduateColumns.length" class="empty-state">结业名单只包含培训已结业且本人考核合格的人员</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ activeTab === 'trainings' ? trainingTotal : graduateTotal }} 条{{ activeTab === 'trainings' ? '培训' : '结业' }}记录</span>
      <span v-if="message" :class="messageOk ? 'success-text' : 'error-text'">{{ message }}</span>
    </footer>

    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <section class="modal wide">
        <header class="modal-head">
          <h3>安排培训演练</h3>
          <button class="icon-btn" type="button" @click="showCreate = false">×</button>
        </header>
        <form class="form-grid" @submit.prevent="submitCreate">
          <label>
            <span>培训编号 *</span>
            <input v-model="createForm.code" placeholder="如：TR-20260925-05" />
          </label>
          <label>
            <span>培训名称 *</span>
            <input v-model="createForm.name" placeholder="如：信号机检修标准流程培训" />
          </label>
          <label>
            <span>岗位 *</span>
            <input v-model="createForm.post" placeholder="如：信号工" />
          </label>
          <label>
            <span>设备类型 *</span>
            <select v-model="createForm.deviceType">
              <option value="">请选择</option>
              <option>信号机</option>
              <option>转辙机</option>
              <option>轨道电路</option>
              <option>联锁设备</option>
            </select>
          </label>
          <label>
            <span>培训日期 *</span>
            <input v-model="createForm.date" type="date" />
          </label>
          <label>
            <span>授课师傅 *</span>
            <input v-model="createForm.instructor" placeholder="师傅姓名" />
          </label>
          <label class="full-span">
            <span>参训人员 *</span>
            <textarea v-model="createForm.names" rows="4" placeholder="多人可用逗号或换行分隔，如：陈小光、孙明"></textarea>
          </label>
          <label>
            <span>操作人 *</span>
            <input v-model="operator" />
          </label>
          <div class="form-actions full-span">
            <button class="btn" type="button" @click="showCreate = false">取消</button>
            <button class="btn primary" type="submit">保存排期</button>
          </div>
        </form>
      </section>
    </div>

    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <section class="modal detail-modal">
        <header class="modal-head">
          <div>
            <h3>{{ detail.培训名称 }}</h3>
            <p>{{ detail.培训编号 }} · {{ detail.岗位 }} · {{ detail.设备类型 }} · {{ detail.status }}</p>
          </div>
          <button class="icon-btn" type="button" @click="closeDetail">×</button>
        </header>

        <div class="detail-toolbar">
          <label>
            当前操作人
            <input v-model="operator" />
          </label>
          <button v-if="detail.status === '培训中'" class="btn primary" type="button" @click="finishDrill(detail.id)">结束演练并进入待考核</button>
          <button class="btn" type="button" @click="loadDetail(detail.id)">刷新详情</button>
        </div>

        <div class="info-grid">
          <div><span>培训日期</span><strong>{{ detail.培训日期 }}</strong></div>
          <div><span>授课师傅</span><strong>{{ detail.授课师傅 }}</strong></div>
          <div><span>创建</span><strong>{{ detail.创建人 }} {{ detail.创建时间 }}</strong></div>
          <div><span>开始培训</span><strong>{{ detail.培训开始人 || '—' }} {{ detail.培训开始时间 || '' }}</strong></div>
          <div><span>结束演练</span><strong>{{ detail.结束演练人 || '—' }} {{ detail.结束演练时间 || '' }}</strong></div>
          <div><span>结业</span><strong>{{ detail.结业操作人 || '—' }} {{ detail.结业时间 || '' }}</strong></div>
        </div>

        <h4>参训人员与考核</h4>
        <table class="data-table inner-table">
          <thead>
            <tr>
              <th>姓名</th>
              <th>签到</th>
              <th>签到人/时间</th>
              <th>人员状态</th>
              <th>考核成绩</th>
              <th>考核结果</th>
              <th>办理</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="person in detail.participants" :key="person.id">
              <td>{{ person.姓名 }}</td>
              <td>{{ person.签到状态 }}</td>
              <td>
                <template v-if="person.签到状态 === '已签到'">{{ person.签到人 }}<br>{{ person.签到时间 }}</template>
                <template v-else>—</template>
              </td>
              <td :class="{ failed: person.考核结果 === '不合格' }">{{ person.人员状态 }}</td>
              <td>
                <input
                  v-if="detail.status === '待考核' && person.签到状态 === '已签到' && !person.score_submitted"
                  v-model="scoreInputs[person.id]"
                  inputmode="decimal"
                  placeholder="0-100"
                />
                <span v-else>{{ person.考核成绩 || (person.签到状态 === '已签到' ? '未填写' : '—') }}</span>
              </td>
              <td :class="{ failed: person.考核结果 === '不合格', passed: person.考核结果 === '合格' }">
                {{ person.考核结果 }}
              </td>
              <td>
                <button
                  v-if="['待开班', '培训中'].includes(String(detail.status)) && person.签到状态 === '未签到'"
                  class="link"
                  type="button"
                  @click="signIn(person.id)"
                >
                  签到
                </button>
                <span v-else-if="person.score_submitted">成绩已锁定</span>
                <span v-else>—</span>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="detail.status === '待考核'" class="score-actions">
          <p class="hint">未填写成绩会逐条提示“不能按合格处理”；同一人重复提交只保留首次生效成绩。合格者个人结业，不合格者留在考核不合格状态。</p>
          <button class="btn primary" type="button" @click="submitScores">提交本页成绩</button>
        </div>

        <div v-if="scoreResults.length" class="result-panel">
          <h4>本次提交逐条结果</h4>
          <ul>
            <li v-for="result in scoreResults" :key="`${result.participantId}-${result.message}`" :class="result.ok ? 'ok' : 'bad'">
              {{ result.participantName || result.participantId }}：{{ result.message }}
            </li>
          </ul>
        </div>

        <h4>流转留痕</h4>
        <table class="data-table inner-table">
          <thead>
            <tr><th>动作</th><th>目标状态</th><th>操作人</th><th>操作时间</th><th>说明</th></tr>
          </thead>
          <tbody>
            <tr v-for="log in detail.logs" :key="String(log.id)">
              <td>{{ log.动作 }}</td>
              <td>{{ log.目标状态 }}</td>
              <td>{{ log.操作人 }}</td>
              <td>{{ log.操作时间 }}</td>
              <td>{{ log.说明 }}</td>
            </tr>
          </tbody>
        </table>

        <footer class="modal-foot">
          <span>返回列表会重新读取服务端状态，已流转的状态不会退回上一档。</span>
          <button class="btn" type="button" @click="closeDetail">返回列表</button>
        </footer>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { useSessionStore } from '@/stores/session'
import { request } from '@/api/client'

type Cell = string | number | null
type Row = Record<string, Cell>
type Participant = Row & {
  id: number
  姓名: string
  签到状态: string
  人员状态: string
  考核成绩: string
  考核结果: string
  score_submitted: boolean
}
type Detail = Row & {
  id: number
  status: string
  participants: Participant[]
  logs: Row[]
}
type ScoreResult = {
  ok: boolean
  participantId: number
  participantName: string
  message: string
  assessmentResult: string
}

const ENDPOINT = '/api/training'
const session = useSessionStore()
const statuses = ['待开班', '培训中', '待考核', '已结业']
const trainingColumns = ['培训编号', '培训名称', '岗位', '设备类型', '培训日期', '授课师傅', '应到人数', '已签到人数', '待考核人数', '合格人数', '不合格人数', '状态']
const graduateColumns = ['培训编号', '培训名称', '岗位', '设备类型', '姓名', '考核成绩', '考核结果', '考核人', '考核时间', '结业时间']

const activeTab = ref<'trainings' | 'graduates'>('trainings')
const trainings = ref<Row[]>([])
const graduates = ref<Row[]>([])
const trainingTotal = ref(0)
const graduateTotal = ref(0)
const message = ref('')
const messageOk = ref(true)
const operator = ref(session.operator)
const filters = reactive({ keyword: '', post: '', deviceType: '', status: '' })
const graduateFilters = reactive({ keyword: '', post: '', deviceType: '' })
const showCreate = ref(false)
const detail = ref<Detail | null>(null)
const scoreInputs = reactive<Record<number, string>>({})
const scoreResults = ref<ScoreResult[]>([])
const createForm = reactive({
  code: '',
  name: '',
  post: '',
  deviceType: '',
  date: '2026-09-25',
  instructor: '',
  names: '',
})

const stats = computed(() => [
  { label: '待开班', value: trainings.value.filter((row) => row.status === '待开班').length },
  { label: '培训中', value: trainings.value.filter((row) => row.status === '培训中').length },
  { label: '待考核', value: trainings.value.filter((row) => row.status === '待考核').length },
  { label: '已结业', value: trainings.value.filter((row) => row.status === '已结业').length },
])

function setMessage(text: string, ok = true) {
  message.value = text
  messageOk.value = ok
}

function queryString(source: Record<string, string>) {
  const params = new URLSearchParams()
  Object.entries(source).forEach(([key, value]) => {
    if (value) params.set(key, value)
  })
  const text = params.toString()
  return text ? `?${text}` : ''
}

async function reloadTrainings() {
  const response = await request(`${ENDPOINT}${queryString({
    keyword: filters.keyword,
    post: filters.post,
    deviceType: filters.deviceType,
    status: filters.status,
  })}`)
  if (!response.ok) throw new Error('培训列表读取失败')
  const payload = await response.json()
  trainings.value = payload.items ?? []
  trainingTotal.value = payload.total ?? trainings.value.length
}

async function reloadGraduates() {
  const response = await request(`${ENDPOINT}/graduates${queryString({
    keyword: graduateFilters.keyword,
    post: graduateFilters.post,
    deviceType: graduateFilters.deviceType,
  })}`)
  if (!response.ok) throw new Error('结业名单读取失败')
  const payload = await response.json()
  graduates.value = payload.items ?? []
  graduateTotal.value = payload.total ?? graduates.value.length
}

async function safeReload() {
  try {
    if (activeTab.value === 'trainings') {
      await reloadTrainings()
    } else {
      await reloadGraduates()
    }
  } catch (error) {
    setMessage(error instanceof Error ? error.message : '列表读取失败', false)
  }
}

function resetFilters() {
  filters.keyword = ''
  filters.post = ''
  filters.deviceType = ''
  filters.status = ''
  void reloadTrainings().catch(() => undefined)
}

function resetGraduateFilters() {
  graduateFilters.keyword = ''
  graduateFilters.post = ''
  graduateFilters.deviceType = ''
  void reloadGraduates().catch(() => undefined)
}

function switchTab(tab: 'trainings' | 'graduates') {
  activeTab.value = tab
  message.value = ''
  void safeReload()
}

function openCreate() {
  message.value = ''
  showCreate.value = true
}

async function submitCreate() {
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({
        values: {
          培训编号: createForm.code,
          培训名称: createForm.name,
          岗位: createForm.post,
          设备类型: createForm.deviceType,
          培训日期: createForm.date,
          授课师傅: createForm.instructor,
          参训人员: createForm.names,
          操作人: operator.value,
        },
      }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) throw new Error(payload.detail || payload.message || '培训排期未保存')
    showCreate.value = false
    Object.assign(createForm, { code: '', name: '', post: '', deviceType: '', date: '2026-09-25', instructor: '', names: '' })
    setMessage(payload.message, true)
    await reloadTrainings()
  } catch (error) {
    setMessage(error instanceof Error ? error.message : '培训排期未保存', false)
  }
}

async function loadDetail(id: number) {
  const response = await request(`${ENDPOINT}/${id}`)
  if (!response.ok) throw new Error('培训详情读取失败')
  detail.value = await response.json() as Detail
  detail.value.participants.forEach((person) => {
    if (!(person.id in scoreInputs)) scoreInputs[person.id] = person.考核成绩 || ''
  })
}

async function openDetail(id: number) {
  message.value = ''
  scoreResults.value = []
  try {
    await loadDetail(id)
  } catch (error) {
    setMessage(error instanceof Error ? error.message : '培训详情读取失败', false)
  }
}

function closeDetail() {
  detail.value = null
  scoreResults.value = []
  void safeReload()
}

async function postAction(path: string, body: object, successText?: string) {
  const response = await request(path, { method: 'POST', body: JSON.stringify(body) })
  const payload = await response.json()
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.detail || payload.message || '操作未生效')
  }
  if (payload.entry) detail.value = payload.entry as Detail
  setMessage(successText || payload.message || '操作已生效', true)
  await reloadTrainings()
  return payload
}

async function signIn(participantId: number) {
  if (!detail.value) return
  try {
    await postAction(`${ENDPOINT}/${detail.value.id}/sign-in`, { operator: operator.value, participantId })
  } catch (error) {
    setMessage(error instanceof Error ? error.message : '签到失败', false)
  }
}

async function finishDrill(id: number, confirmFirst = false) {
  try {
    if (confirmFirst && !window.confirm('结束演练后将进入待考核，状态不能退回培训中。确认继续？')) return
    if (!detail.value || detail.value.id !== id) await loadDetail(id)
    await postAction(`${ENDPOINT}/${id}/finish-drill`, { operator: operator.value })
  } catch (error) {
    setMessage(error instanceof Error ? error.message : '结束演练失败', false)
  }
}

async function submitScores() {
  if (!detail.value) return
  if (!window.confirm('提交后的首次成绩将锁定，重复提交不会覆盖。确认提交？')) return
  const results = detail.value.participants
    .filter((person) => person.签到状态 === '已签到' && !person.score_submitted)
    .map((person) => ({ participantId: person.id, score: scoreInputs[person.id] ?? '' }))
  try {
    const response = await request(`${ENDPOINT}/${detail.value.id}/scores`, {
      method: 'POST',
      body: JSON.stringify({ operator: operator.value, results }),
    })
    const payload = await response.json()
    if (!response.ok) throw new Error(payload.detail || payload.message || '成绩提交失败')
    scoreResults.value = payload.results ?? []
    if (payload.entry) detail.value = payload.entry as Detail
    setMessage(payload.message, Boolean(payload.ok))
    await reloadTrainings()
  } catch (error) {
    setMessage(error instanceof Error ? error.message : '成绩提交失败', false)
  }
}

onMounted(() => {
  void reloadTrainings().catch((error: unknown) => {
    setMessage(error instanceof Error ? error.message : '培训列表读取失败', false)
  })
})
</script>

<style scoped>
.training-page .page-actions { display: flex; gap: 8px; }
.tabs { display: flex; gap: 8px; margin: 0 0 12px; }
.tabs button { border: 1px solid var(--border); background: #fff; padding: 7px 16px; border-radius: 6px; cursor: pointer; }
.tabs button.active { background: var(--brand); border-color: var(--brand); color: #fff; }
.success-text { color: #027a48; }
.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.48); display: flex; align-items: center; justify-content: center; z-index: 20; padding: 24px; }
.modal { background: #fff; border-radius: 10px; width: min(680px, 100%); max-height: 92vh; overflow: auto; box-shadow: 0 20px 60px rgba(15, 23, 42, 0.28); }
.modal.wide { width: min(820px, 100%); }
.detail-modal { width: min(1180px, 100%); }
.modal-head { display: flex; justify-content: space-between; align-items: flex-start; padding: 16px 18px; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: #fff; z-index: 1; }
.modal-head h3 { margin: 0; font-size: 18px; }
.modal-head p { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
.icon-btn { border: none; background: none; font-size: 24px; line-height: 1; cursor: pointer; color: var(--muted); }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; padding: 18px; }
.form-grid label, .detail-toolbar label { display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: var(--muted); }
.form-grid input, .form-grid select, .form-grid textarea, .detail-toolbar input { border: 1px solid var(--border); border-radius: 6px; padding: 8px; font: inherit; color: #1f2937; }
.full-span { grid-column: 1 / -1; }
.form-actions { display: flex; justify-content: flex-end; gap: 8px; }
.detail-toolbar { display: flex; align-items: flex-end; gap: 12px; padding: 14px 18px; }
.detail-toolbar input { min-width: 160px; }
.info-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; padding: 0 18px 12px; }
.info-grid div { background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 9px; }
.info-grid span { display: block; color: var(--muted); font-size: 12px; margin-bottom: 4px; }
.info-grid strong { font-size: 13px; word-break: break-all; }
.modal h4 { margin: 12px 18px 8px; }
.inner-table { width: calc(100% - 36px); margin: 0 18px 12px; }
.inner-table input { width: 86px; padding: 5px; border: 1px solid var(--border); border-radius: 4px; }
.failed { color: #b42318; font-weight: 600; }
.passed { color: #027a48; font-weight: 600; }
.score-actions { margin: 0 18px 12px; padding: 12px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.hint { margin: 0; color: #92400e; font-size: 12px; }
.result-panel { margin: 0 18px 12px; border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; }
.result-panel h4 { margin: 0 0 8px; }
.result-panel ul { margin: 0; padding-left: 18px; font-size: 13px; }
.result-panel li.ok { color: #027a48; }
.result-panel li.bad { color: #b42318; }
.modal-foot { position: sticky; bottom: 0; display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 18px; border-top: 1px solid var(--border); background: #fff; color: var(--muted); font-size: 12px; }
@media (max-width: 900px) {
  .form-grid, .info-grid { grid-template-columns: 1fr; }
  .detail-modal { width: 100%; }
}
</style>
