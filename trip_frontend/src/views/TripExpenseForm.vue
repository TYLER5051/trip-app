<script setup>
import { ref, computed, watch } from 'vue'
import { formatMoney, toDecimalString } from '../utils/money'
import UserAvatar from '../components/UserAvatar.vue'

const props = defineProps({
  members: { type: Array, required: true },
  currentUserId: { type: Number, required: true },
  expense: { type: Object, default: null },
  isSaving: { type: Boolean, default: false }
})

const emit = defineEmits(['save', 'close'])

const name = ref('')
const amount = ref('')
const paidFromPool = ref(true)
const paidByUserId = ref(null)
const note = ref('')
const rows = ref([])

function buildRows(expense) {
  const preset = new Map()
  if (expense) {
    for (const s of expense.shares || []) {
      if (s.user) preset.set(s.user.id, Number(s.amount))
    }
  }
  rows.value = props.members.map(m => ({
    user_id: m.id,
    username: m.username,
    checked: expense ? preset.has(m.id) : true,
    amount: toDecimalString(preset.get(m.id) ?? 0)
  }))
}

watch(
  () => props.expense,
  (expense) => {
    if (!expense) {
      paidFromPool.value = true
      paidByUserId.value = props.currentUserId
      buildRows(null)
      return
    }
    name.value = expense.name || ''
    amount.value = String(expense.amount ?? '')
    paidFromPool.value = expense.paid_from_pool !== false
    paidByUserId.value = expense.paid_by_user?.id ?? props.currentUserId
    note.value = expense.note || ''
    buildRows(expense)
  },
  { immediate: true }
)

const amountNum = computed(() => {
  const n = Number(amount.value)
  return Number.isFinite(n) && n > 0 ? n : 0
})

const checkedRows = computed(() => rows.value.filter(r => r.checked))

const sharesSum = computed(() =>
  checkedRows.value.reduce((sum, r) => sum + (Number(r.amount) || 0), 0)
)

const remainder = computed(() => Number((sharesSum.value - amountNum.value).toFixed(2)))

const canSave = computed(() => {
  const validName = name.value.trim().length >= 2
  const validAmount = amountNum.value > 0
  const validShares =
    checkedRows.value.length > 0 &&
    checkedRows.value.every(r => Number(r.amount) > 0) &&
    Math.abs(remainder.value) < 0.005
  const validPayer = paidFromPool.value || Number(paidByUserId.value) > 0
  return validName && validAmount && validShares && validPayer
})

// Порівну: залишок від ділення додаємо першим учасникам, щоб сума часток точно сходилася.
const splitEqually = () => {
  const checked = checkedRows.value
  const totalCents = Math.round(amountNum.value * 100)
  if (!checked.length || totalCents <= 0) return
  const count = checked.length
  const base = Math.floor(totalCents / count)
  const extra = totalCents - base * count
  checked.forEach((row, i) => {
    row.amount = ((base + (i < extra ? 1 : 0)) / 100).toFixed(2)
  })
}

const submit = () => {
  if (!canSave.value || props.isSaving) return
  const payload = {
    name: name.value.trim(),
    amount: toDecimalString(amountNum.value),
    paid_from_pool: paidFromPool.value,
    shares: checkedRows.value.map(r => ({ user_id: r.user_id, amount: toDecimalString(r.amount) }))
  }
  if (!paidFromPool.value) payload.paid_by_user_id = Number(paidByUserId.value)
  if (note.value.trim()) payload.note = note.value.trim()
  emit('save', payload)
}
</script>

<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="expense-modal">
      <h3>{{ expense ? 'Редагувати витрату' : 'Додати витрату' }}</h3>

      <form @submit.prevent="submit">
        <label class="field">
          <span>Назва</span>
          <input v-model="name" type="text" placeholder="напр., Продукти" required />
        </label>

        <label class="field">
          <span>Сума, ₴</span>
          <input v-model="amount" type="number" step="0.01" min="0" placeholder="0.00" required />
        </label>

        <div class="field">
          <span>Хто оплатив</span>
          <div class="radio-row">
            <label>
              <input v-model="paidFromPool" type="radio" :value="true" />
              Зі спільного банку
            </label>
            <label>
              <input v-model="paidFromPool" type="radio" :value="false" />
              Один учасник
            </label>
          </div>
          <select v-if="!paidFromPool" v-model="paidByUserId" class="payer-select">
            <option v-for="m in members" :key="m.id" :value="m.id">{{ m.username }}</option>
          </select>
        </div>

        <div class="field">
          <span>Розподіл між учасниками</span>
          <div class="split-toolbar">
            <button type="button" class="split-btn" @click="splitEqually">⟳ Розділити порівну</button>
          </div>

          <ul class="share-list">
            <li v-for="row in rows" :key="row.user_id" class="share-row" :class="{ off: !row.checked }">
              <label class="share-check">
                <input v-model="row.checked" type="checkbox" />
                <UserAvatar :username="row.username" :size="22" />
                <span>{{ row.username }}</span>
              </label>
              <input
                v-model.number="row.amount"
                type="number"
                step="0.01"
                min="0"
                :disabled="!row.checked"
                class="share-amount"
              />
            </li>
          </ul>

          <div class="sum-row" :class="{ bad: Math.abs(remainder) >= 0.005 }">
            <span>Сума часток: {{ formatMoney(sharesSum) }}</span>
            <span v-if="Math.abs(remainder) >= 0.005" class="sum-diff">
              <template v-if="remainder < 0">не вистачає {{ formatMoney(-remainder) }}</template>
              <template v-else>перевищує на {{ formatMoney(remainder) }}</template>
            </span>
            <span v-else class="sum-ok">✓ сходиться</span>
          </div>
        </div>

        <label class="field">
          <span>Примітка (необов'язково)</span>
          <input v-model="note" type="text" maxlength="200" placeholder="деталі витрати" />
        </label>

        <div class="modal-actions">
          <button type="button" class="btn-cancel" :disabled="isSaving" @click="$emit('close')">
            Скасувати
          </button>
          <button type="submit" class="btn-save" :disabled="!canSave || isSaving">
            {{ isSaving ? 'Збереження...' : 'Зберегти' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.expense-modal {
  background: white;
  border-radius: 12px;
  padding: 25px;
  width: min(480px, 92vw);
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}
.expense-modal h3 {
  margin: 0 0 14px;
  color: #2c3e50;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 14px;
  font-size: 13px;
  color: #34495e;
}
.field > span {
  font-weight: bold;
}
.field input[type="text"],
.field input[type="number"],
.field select {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 5px;
  font-size: 14px;
}
.radio-row {
  display: flex;
  gap: 16px;
  font-size: 14px;
}
.radio-row label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-weight: normal;
}
.payer-select {
  margin-top: 6px;
}
.split-toolbar {
  margin-bottom: 8px;
}
.split-btn {
  background: #eaf6ff;
  color: #3498db;
  border: 1px dashed #3498db;
  padding: 6px 12px;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
  font-size: 12px;
}
.split-btn:hover {
  background: #d4ecff;
}
.share-list {
  list-style: none;
  margin: 0 0 10px;
  padding: 0;
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid #eee;
  border-radius: 8px;
}
.share-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 6px 10px;
  border-bottom: 1px solid #f2f4f6;
}
.share-row:last-child {
  border-bottom: none;
}
.share-row.off {
  opacity: 0.55;
}
.share-check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  cursor: pointer;
  min-width: 0;
}
.share-amount {
  width: 90px;
  padding: 6px;
  border: 1px solid #ccc;
  border-radius: 5px;
  font-size: 14px;
  text-align: right;
}
.share-amount:disabled {
  background: #f2f4f6;
}
.sum-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #27ae60;
  font-weight: bold;
}
.sum-row.bad {
  color: #e74c3c;
}
.sum-diff {
  color: #e74c3c;
}
.sum-ok {
  color: #27ae60;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}
.btn-cancel {
  background: #ecf0f1;
  color: #34495e;
  border: none;
  padding: 9px 18px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
.btn-cancel:hover:not(:disabled) {
  background: #dde3e7;
}
.btn-save {
  background-color: #42b883;
  color: white;
  border: none;
  padding: 9px 18px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
.btn-save:hover:not(:disabled) {
  background-color: #35495e;
}
.modal-actions button:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
