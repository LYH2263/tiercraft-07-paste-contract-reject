<script setup>
import { computed, onMounted, ref } from 'vue'
import { getJson, postJson, putJson } from '../api'

const domains = ref([])
const selectedId = ref(null)
const contract = ref([])
const types = ref(['文本', '数值', '整数', '日期'])
const rejects = ref([])
const err = ref('')
const msg = ref('')
const busy = ref(false)

const selected = computed(() => domains.value.find(d => d.id === selectedId.value))

async function loadContract() {
  if (!selectedId.value) return
  const data = await getJson(`/api/domains/${selectedId.value}/contract`)
  contract.value = data.fields.map(f => ({ ...f }))
  types.value = data.types
}

async function loadRejects() {
  if (!selectedId.value) return
  rejects.value = await getJson(`/api/domains/${selectedId.value}/rejects`)
}

async function selectDomain(id) {
  selectedId.value = id
  msg.value = ''
  err.value = ''
  await Promise.all([loadContract(), loadRejects()])
}

function addField() {
  contract.value.push({ field: '', required: true, ftype: '文本' })
}

function removeField(i) {
  contract.value.splice(i, 1)
}

async function saveContract() {
  busy.value = true
  err.value = ''
  msg.value = ''
  try {
    const data = await putJson(`/api/domains/${selectedId.value}/contract`, { fields: contract.value })
    contract.value = data.fields.map(f => ({ ...f }))
    msg.value = '契约已保存，重新装载贴源后按新契约校验。'
  } catch (e) {
    err.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}

async function reload() {
  busy.value = true
  err.value = ''
  msg.value = ''
  try {
    const job = await postJson('/api/jobs/load-paste', { domain_id: selectedId.value })
    msg.value = `装载完成：输入${job.in_count}行，写入贴源${job.out_count}行，契约拒收${job.drop_count}行。`
    await loadRejects()
  } catch (e) {
    err.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  try {
    domains.value = await getJson('/api/domains')
    if (domains.value.length) await selectDomain(domains.value[0].id)
  } catch (e) {
    err.value = String(e.message || e)
  }
})
</script>
<template>
  <div>
    <h2>主题域</h2>
    <p class="lead">每个主题域对应一套贴源夹具、业务键与字段契约，分层建设围绕主题域推进。</p>
    <p v-if="err" class="err">{{ err }}</p>
    <p v-if="msg" class="ok">{{ msg }}</p>
    <div class="panel">
      <table>
        <thead>
          <tr><th>编号</th><th>名称</th><th>业务键</th><th>夹具文件</th><th>说明</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="d in domains" :key="d.id" :class="{ picked: d.id === selectedId }">
            <td>{{ d.id }}</td>
            <td>{{ d.name }}</td>
            <td>{{ d.biz_key }}</td>
            <td>{{ d.fixture_file }}</td>
            <td>{{ d.description }}</td>
            <td>
              <button class="secondary btn-small" @click="selectDomain(d.id)">契约与拒收</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <template v-if="selected">
      <div class="panel">
        <h3>字段契约 — {{ selected.name }}</h3>
        <p class="muted">
          装载逐行校验：缺必填、类型不符或含未声明字段的行不进贴源层，一律进契约拒收清单。
        </p>
        <table class="contract-table">
          <thead>
            <tr><th>字段名</th><th>必填</th><th>类型</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="(f, i) in contract" :key="i">
              <td><input type="text" v-model.trim="f.field" placeholder="源字段名" /></td>
              <td><input type="checkbox" v-model="f.required" /></td>
              <td>
                <select v-model="f.ftype">
                  <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
                </select>
              </td>
              <td><button class="secondary btn-small" @click="removeField(i)">删除</button></td>
            </tr>
          </tbody>
        </table>
        <div class="toolbar">
          <button class="secondary" :disabled="busy" @click="addField">添加字段</button>
          <button :disabled="busy" @click="saveContract">保存契约</button>
          <button class="secondary" :disabled="busy" @click="reload">重新装载贴源</button>
        </div>
      </div>

      <div class="panel">
        <h3>契约拒收清单 — {{ selected.name }}（{{ rejects.length }} 行）</h3>
        <table v-if="rejects.length">
          <thead>
            <tr><th>编号</th><th>行号</th><th>拒收原因</th><th>原始行</th><th>时间</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in rejects" :key="r.id">
              <td>{{ r.id }}</td>
              <td>{{ r.line_no }}</td>
              <td class="warn">{{ r.reason }}</td>
              <td class="raw">{{ r.raw_json }}</td>
              <td>{{ r.created_at }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="muted">暂无拒收行，最近一次装载全部合规。</p>
      </div>
    </template>
  </div>
</template>
