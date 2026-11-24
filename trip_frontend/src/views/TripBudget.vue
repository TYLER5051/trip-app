<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { toast } from 'vue3-toastify'
import api from '../services/api'
import { formatMoney, toDecimalString } from '../utils/money'
import TripExpenseForm from './TripExpenseForm.vue'
import TripSettlement from './TripSettlement.vue'
import UserAvatar from '../components/UserAvatar.vue'

const props = defineProps({
  tripId: { type: Number, required: true },
  members: { type: Array, required: true },
  currentUserId: { type: Number, required: true },
  ownerId: { type: Number, required: false, default: null },
  isArchived: { type: Boolean, default: false }
})

const emit = defineEmits(['changed'])

const LIMIT = 100
const isLoading = ref(true)
const isLoadingMore = ref(false)
const isSavingContribution = ref(false)
const isSavingExpense = ref(false)
const isDeleting = ref(false)

const overview = ref(null)
const contributions = ref([])
const expenses = ref([])
const total = ref(0)
const offset = ref(0)

const hasMore = computed(() => contributions.value.length + expenses.value.length < total.value)

const contributionModal = ref(null)
const showExpenseForm = ref(false)
const editingExpense = ref(null)
const showSettlementModal = ref(false)
const isSettlementLoading = ref(false)
const settlement = ref(null)

const contributionAmount = ref('')
const contributionNote = ref('')

const budgetUrl = () => `/trips/${props.tripId}/budget`

const canManageContribution = (c) =>
  props.currentUserId === props.ownerId || props.currentUserId === c.user?.id

const canManageExpense = (e) =>
  props.currentUserId === props.ownerId || props.currentUserId === e.created_by?.id

function formatDate(iso) {
  return new Date(iso).toLocaleString('uk-UA', { dateStyle: 'short', timeStyle: 'short' })
}

function usernameOf(user) {
  return user?.username || 'Видалений користувач'
}

const fetchOverview = async () => {
  overview.value = await api.get(`${budgetUrl()}/overview`)
}

const appendUnique = (list, newItems) => {
  const seen = new Set(list.value.map(x => x.id))
  newItems.forEach(x => {
    if (!seen.has(x.id)) {
      list.value.push(x)
      seen.add(x.id)
    }
  })
}

const fetchList = async (reset) => {
  if (reset) {
    contributions.value = []
    expenses.value = []
    offset.value = 0
    total.value = 0
  }
  const params = new URLSearchParams({ limit: String(LIMIT), offset: String(offset.value) })
  const data = await api.get(`${budgetUrl()}/?${params.toString()}`)
  if (reset) {
    contributions.value = data.contributions
    expenses.value = data.expenses
  } else {
    appendUnique(contributions, data.contributions)
    appendUnique(expenses, data.expenses)
  }
  total.value = data.total
  offset.value += LIMIT
}

const loadBudget = async () => {
  isLoading.value = true
  try {
    await Promise.all([fetchList(true), fetchOverview()])
  } catch (error) {
    toast.error(error.message)
  } finally {
    isLoading.value = false
  }
}

const loadMore = async () => {
  isLoadingMore.value = true
  try {
    await fetchList(false)
  } catch (error) {
    toast.error(error.message)
  } finally {
    isLoadingMore.value = false
  }
}

const refresh = async () => {
  await loadBudget()
  emit('changed')
}

const openAddContribution = () => {
  contributionModal.value = { mode: 'create', record: null }
}

const openEditContribution = (record) => {
  contributionModal.value = { mode: 'edit', record }
}

const closeContributionModal = () => {
  if (!isSavingContribution.value) contributionModal.value = null
}

watch(contributionModal, (modal) => {
  if (!modal) return
  contributionAmount.value = modal.record ? String(modal.record.amount ?? '') : ''
  contributionNote.value = modal.record?.note || ''
})

const contributionAmountNum = computed(() => {
  const n = Number(contributionAmount.value)
  return Number.isFinite(n) && n > 0 ? n : 0
})

const canSubmitContribution = computed(() => contributionAmountNum.value > 0)

const submitContribution = () => {
  if (!canSubmitContribution.value || isSavingContribution.value) return
  saveContribution({ amount: contributionAmountNum.value, note: contributionNote.value })
}

const saveContribution = async ({ amount, note }) => {
  const isEdit = contributionModal.value?.mode === 'edit'
  isSavingContribution.value = true
  try {
    const body = { amount: toDecimalString(amount), note: note.trim() || null }
    if (isEdit) {
      await api.patch(`${budgetUrl()}/contributions/${contributionModal.value.record.id}`, body)
    } else {
      await api.post(`${budgetUrl()}/contributions`, body)
    }
    toast.success(isEdit ? 'Внесок оновлено.' : 'Внесок додано до банку.')
    contributionModal.value = null
    await refresh()
  } catch (error) {
    toast.error(error.message)
  } finally {
    isSavingContribution.value = false
  }
}

const deleteContribution = async (record) => {
  if (!confirm(`Видалити внесок ${formatMoney(record.amount)}? Банк зменшиться на цю суму.`)) return
  isDeleting.value = true
  try {
    await api.delete(`${budgetUrl()}/contributions/${record.id}`)
    toast.success('Внесок видалено.')
    await refresh()
  } catch (error) {
    toast.error(error.message)
  } finally {
    isDeleting.value = false
  }
}

const openAddExpense = () => {
  editingExpense.value = null
  showExpenseForm.value = true
}

const openEditExpense = (record) => {
  editingExpense.value = record
  showExpenseForm.value = true
}

const closeExpenseForm = () => {
  if (isSavingExpense.value) return
  showExpenseForm.value = false
  editingExpense.value = null
}

const saveExpense = async (payload) => {
  const isEdit = !!editingExpense.value
  isSavingExpense.value = true
  try {
    if (isEdit) {
      await api.patch(`${budgetUrl()}/expenses/${editingExpense.value.id}`, payload)
    } else {
      await api.post(`${budgetUrl()}/expenses`, payload)
    }
    toast.success(isEdit ? 'Витрату оновлено.' : 'Витрату додано.')
    showExpenseForm.value = false
    editingExpense.value = null
    await refresh()
  } catch (error) {
    toast.error(error.message)
  } finally {
    isSavingExpense.value = false
  }
}

const deleteExpense = async (record) => {
  if (!confirm(`Видалити витрату «${record.name}» на ${formatMoney(record.amount)}?`)) return
  isDeleting.value = true
  try {
    await api.delete(`${budgetUrl()}/expenses/${record.id}`)
    toast.success('Витрату видалено.')
    await refresh()
  } catch (error) {
    toast.error(error.message)
  } finally {
    isDeleting.value = false
  }
}

const openSettlement = async () => {
  showSettlementModal.value = true
  settlement.value = null
  isSettlementLoading.value = true
  try {
    settlement.value = await api.get(`${budgetUrl()}/settlement`)
  } catch (error) {
    toast.error(error.message)
    showSettlementModal.value = false
  } finally {
    isSettlementLoading.value = false
  }
}

onMounted(loadBudget)
</script>

<template>
  <div class="budget-card">
    <div v-if="isLoading && !overview" class="budget-loading">Завантаження бюджету...</div>

    <template v-else>
      <div v-if="overview" class="overview-grid">
        <div class="overview-item">
          <span class="ov-label">Внесено в банк</span>
          <span class="ov-value">{{ formatMoney(overview.total_contributions) }}</span>
        </div>
        <div class="overview-item">
          <span class="ov-label">Витрачено</span>
          <span class="ov-value">{{ formatMoney(overview.total_expenses) }}</span>
        </div>
        <div class="overview-item bank">
          <span class="ov-label">Залишок у банку</span>
          <span class="ov-value" :class="{ negative: Number(overview.bank_balance) < 0 }">
            {{ formatMoney(overview.bank_balance) }}
          </span>
        </div>
      </div>

      <div class="budget-actions">
        <button v-if="!isArchived" class="budget-action-btn" @click="openAddContribution">➕ Внести кошти</button>
        <button v-if="!isArchived" class="budget-action-btn" @click="openAddExpense">🧾 Додати витрату</button>
        <button class="budget-action-btn" @click="openSettlement">🧮 Розрахунки</button>
      </div>

      <div v-if="overview?.participants?.length" class="balances-card">
        <h4>Баланси учасників</h4>
        <ul class="balances-list">
          <li v-for="p in overview.participants" :key="p.user?.id" class="balance-row">
            <UserAvatar :username="p.user?.username" :color="p.user?.avatar_color" :size="24" />
            <span class="balance-name">{{ usernameOf(p.user) }}</span>
            <span class="balance-sub">
              внески {{ formatMoney(p.contributed) }} · оплати {{ formatMoney(p.paid_by_self) }} · частки {{ formatMoney(p.share_costs) }}
            </span>
            <span class="balance-net" :class="{ positive: Number(p.net) > 0, negative: Number(p.net) < 0 }">
              {{ Number(p.net) >= 0 ? '+' : '' }}{{ formatMoney(p.net) }}
            </span>
          </li>
        </ul>
        <p v-if="overview.deleted_users && Number(overview.deleted_users.net) !== 0" class="deleted-note">
          Кошти видалених учасників ({{ formatMoney(overview.deleted_users.net) }}) враховуються в розрахунках окремо.
        </p>
      </div>

      <div class="entries">
        <section class="entries-section">
          <h4>Внески в банк</h4>
          <p v-if="contributions.length === 0" class="entries-empty">Поки що немає внесків.</p>
          <ul v-else class="entry-list">
            <li v-for="c in contributions" :key="'c' + c.id" class="entry-row">
              <UserAvatar :username="c.user?.username" :color="c.user?.avatar_color" :size="28" />
              <div class="entry-main">
                <div class="entry-title">
                  <strong>{{ usernameOf(c.user) }}</strong>
                  <span class="entry-amount plus">+ {{ formatMoney(c.amount) }}</span>
                </div>
                <div class="entry-meta">
                  <span v-if="c.note">{{ c.note }}</span>
                  <span class="entry-date">{{ formatDate(c.created_at) }}</span>
                </div>
              </div>
              <div v-if="!isArchived && canManageContribution(c)" class="entry-actions">
                <button class="icon-btn" title="Редагувати" @click="openEditContribution(c)">✏️</button>
                <button class="icon-btn" title="Видалити" :disabled="isDeleting" @click="deleteContribution(c)">🗑️</button>
              </div>
            </li>
          </ul>
        </section>

        <section class="entries-section">
          <h4>Витрати</h4>
          <p v-if="expenses.length === 0" class="entries-empty">Поки що немає витрат.</p>
          <ul v-else class="entry-list">
            <li v-for="e in expenses" :key="'e' + e.id" class="entry-row">
              <UserAvatar :username="e.created_by?.username" :color="e.created_by?.avatar_color" :size="28" />
              <div class="entry-main">
                <div class="entry-title">
                  <strong>{{ e.name }}</strong>
                  <span class="entry-amount">{{ formatMoney(e.amount) }}</span>
                </div>
                <div class="entry-meta">
                  <span class="entry-badge" :class="e.paid_from_pool ? 'pool' : 'personal'">
                    {{ e.paid_from_pool ? 'з банку' : `оплатив ${usernameOf(e.paid_by_user)}` }}
                  </span>
                  <span v-if="e.note">{{ e.note }}</span>
                  <span class="entry-date">{{ formatDate(e.created_at) }}</span>
                </div>
                <div v-if="e.shares?.length" class="entry-shares">
                  <span v-for="(s, i) in e.shares" :key="'s' + i" class="share-chip">
                    {{ usernameOf(s.user) }}: {{ formatMoney(s.amount) }}
                  </span>
                </div>
              </div>
              <div v-if="!isArchived && canManageExpense(e)" class="entry-actions">
                <button class="icon-btn" title="Редагувати" @click="openEditExpense(e)">✏️</button>
                <button class="icon-btn" title="Видалити" :disabled="isDeleting" @click="deleteExpense(e)">🗑️</button>
              </div>
            </li>
          </ul>
        </section>

        <button v-if="hasMore" class="load-more" :disabled="isLoadingMore" @click="loadMore">
          {{ isLoadingMore ? 'Завантаження...' : `Показати ще (${total - contributions.length - expenses.length})` }}
        </button>
      </div>

      <!-- модалка внеску -->
      <div v-if="contributionModal" class="modal-overlay" @click.self="closeContributionModal">
        <div class="contribution-modal">
          <h3>{{ contributionModal.mode === 'edit' ? 'Редагувати внесок' : 'Внести кошти в банк' }}</h3>
          <form @submit.prevent="submitContribution">
            <label class="field">
              <span>Сума, ₴</span>
              <input v-model="contributionAmount" type="number" step="0.01" min="0.01" placeholder="0.00" required />
            </label>
            <label class="field">
              <span>Примітка (необов'язково)</span>
              <input v-model="contributionNote" type="text" maxlength="200" placeholder="напр., за пальне" />
            </label>
            <div class="modal-actions">
              <button type="button" class="btn-cancel" :disabled="isSavingContribution" @click="closeContributionModal">
                Скасувати
              </button>
              <button type="submit" class="btn-save" :disabled="!canSubmitContribution || isSavingContribution">
                {{ isSavingContribution ? 'Збереження...' : 'Зберегти' }}
              </button>
            </div>
          </form>
        </div>
      </div>

      <!-- модалка витрати -->
      <TripExpenseForm
        v-if="showExpenseForm"
        :members="members"
        :current-user-id="currentUserId"
        :expense="editingExpense"
        :is-saving="isSavingExpense"
        @save="saveExpense"
        @close="closeExpenseForm"
      />

      <!-- модалка розрахунків -->
      <div v-if="showSettlementModal && isSettlementLoading" class="modal-overlay">
        <div class="settlement-modal">
          <h3>🧮 Взаєморозрахунки</h3>
          <p class="settlement-loading">Розрахунок...</p>
        </div>
      </div>
      <TripSettlement
        v-else-if="showSettlementModal && settlement"
        :settlement="settlement"
        @close="showSettlementModal = false"
      />
    </template>
  </div>
</template>

<style scoped>
.budget-card {
  background: white;
  border-radius: 10px;
  padding: 20px 24px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
  margin-top: 20px;
}
.budget-loading {
  color: #7f8c8d;
  text-align: center;
  padding: 20px;
}
.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.overview-item {
  background: #f1f2f6;
  border-radius: 8px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.overview-item.bank {
  background: #eafaf1;
}
.ov-label {
  font-size: 12px;
  color: #7f8c8d;
  font-weight: bold;
}
.ov-value {
  font-size: 20px;
  font-weight: bold;
  color: #2c3e50;
}
.ov-value.negative {
  color: #e74c3c;
}
.budget-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 18px;
}
.budget-action-btn {
  background: #42b883;
  color: white;
  border: none;
  padding: 9px 16px;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  font-size: 13px;
}
.budget-action-btn:hover {
  background: #35495e;
}
.balances-card {
  border: 1px solid #e1e8ed;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 20px;
}
.balances-card h4,
.entries-section h4 {
  margin: 0 0 8px;
  color: #34495e;
  font-size: 14px;
}
.balances-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.balance-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid #f2f4f6;
  font-size: 13px;
}
.balance-row:last-child {
  border-bottom: none;
}
.balance-name {
  font-weight: bold;
  color: #2c3e50;
  white-space: nowrap;
}
.balance-sub {
  color: #7f8c8d;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.balance-net {
  font-weight: bold;
  white-space: nowrap;
}
.balance-net.positive {
  color: #27ae60;
}
.balance-net.negative {
  color: #e74c3c;
}
.deleted-note {
  background: #fff8e1;
  border: 1px solid #f1c40f;
  color: #7d6608;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  margin: 10px 0 0;
}
.entries-section {
  margin-bottom: 24px;
}
.entries-empty {
  color: #7f8c8d;
  font-size: 13px;
}
.entry-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.entry-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #f2f4f6;
}
.entry-row:last-child {
  border-bottom: none;
}
.entry-main {
  flex: 1;
  min-width: 0;
}
.entry-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.entry-title strong {
  color: #2c3e50;
}
.entry-amount {
  font-weight: bold;
  color: #2c3e50;
}
.entry-amount.plus {
  color: #27ae60;
}
.entry-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  align-items: center;
  font-size: 12px;
  color: #7f8c8d;
  margin-top: 2px;
}
.entry-badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: bold;
  font-size: 11px;
}
.entry-badge.pool {
  background: #eafaf1;
  color: #1e8449;
}
.entry-badge.personal {
  background: #eaf2fd;
  color: #2471a3;
}
.entry-date {
  white-space: nowrap;
}
.entry-shares {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 5px;
}
.share-chip {
  background: #f1f2f6;
  border-radius: 10px;
  padding: 2px 8px;
  font-size: 11px;
  color: #34495e;
}
.entry-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 15px;
  opacity: 0.6;
  padding: 2px 4px;
}
.icon-btn:hover:not(:disabled) {
  opacity: 1;
}
.icon-btn:disabled {
  opacity: 0.35;
  cursor: default;
}
.load-more {
  display: block;
  margin: 10px auto 0;
  background-color: #42b883;
  color: white;
  border: none;
  padding: 8px 20px;
  border-radius: 16px;
  font-weight: bold;
  cursor: pointer;
  font-size: 13px;
}
.load-more:hover:not(:disabled) {
  background-color: #35495e;
}
.load-more:disabled {
  opacity: 0.6;
  cursor: default;
}
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.contribution-modal {
  background: white;
  border-radius: 12px;
  padding: 25px;
  width: min(400px, 92vw);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}
.contribution-modal h3 {
  margin: 0 0 14px;
  color: #2c3e50;
}
.settlement-modal {
  background: white;
  border-radius: 12px;
  padding: 25px;
  width: min(460px, 92vw);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}
.settlement-modal h3 {
  margin: 0 0 10px;
  color: #2c3e50;
}
.settlement-loading {
  color: #7f8c8d;
  text-align: center;
  padding: 12px 0;
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
.field input[type="number"] {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 5px;
  font-size: 14px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
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
