<script setup>
import { computed } from 'vue'
import { formatMoney } from '../utils/money'
import UserAvatar from '../components/UserAvatar.vue'

const props = defineProps({
  settlement: { type: Object, required: true }
})
const emit = defineEmits(['close'])

const payouts = computed(() => props.settlement.bank_payouts || [])
const transfers = computed(() => props.settlement.transfers || [])
const isEmpty = computed(() => payouts.value.length === 0 && transfers.value.length === 0)

function usernameOf(user) {
  return user?.username || 'Видалений користувач'
}
</script>

<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="settlement-modal">
      <h3>🧮 Взаєморозрахунки</h3>

      <div class="bank-balance">
        Залишок у банку: <strong>{{ formatMoney(settlement.bank_balance) }}</strong>
      </div>

      <template v-if="isEmpty">
        <p class="settlement-empty">🎉 Усі розрахунки вже проведені — ніхто нікому не винен.</p>
      </template>

      <template v-else>
        <section v-if="payouts.length" class="settlement-section">
          <h4>Виплати з банку</h4>
          <ul class="settlement-list">
            <li v-for="(p, i) in payouts" :key="'p' + i" class="settlement-row">
              <UserAvatar :username="p.user?.username" :color="p.user?.avatar_color" :size="26" />
              <span class="who">{{ usernameOf(p.user) }}</span>
              <span class="amount plus">+ {{ formatMoney(p.amount) }}</span>
            </li>
          </ul>
        </section>

        <section v-if="transfers.length" class="settlement-section">
          <h4>Перекази між учасниками</h4>
          <ul class="settlement-list">
            <li v-for="(t, i) in transfers" :key="'t' + i" class="settlement-row transfer">
              <UserAvatar :username="t.from_user?.username" :color="t.from_user?.avatar_color" :size="26" />
              <span class="who">{{ usernameOf(t.from_user) }}</span>
              <span class="arrow">→</span>
              <UserAvatar :username="t.to_user?.username" :color="t.to_user?.avatar_color" :size="26" />
              <span class="who">{{ usernameOf(t.to_user) }}</span>
              <span class="amount">{{ formatMoney(t.amount) }}</span>
            </li>
          </ul>
        </section>

        <p v-if="settlement.deleted_users_note" class="deleted-note">{{ settlement.deleted_users_note }}</p>
      </template>

      <div class="modal-actions">
        <button type="button" class="btn-cancel" @click="emit('close')">Закрити</button>
      </div>
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
.settlement-modal {
  background: white;
  border-radius: 12px;
  padding: 25px;
  width: min(460px, 92vw);
  max-height: 88vh;
  overflow-y: auto;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}
.settlement-modal h3 {
  margin: 0 0 10px;
  color: #2c3e50;
}
.bank-balance {
  background: #eafaf1;
  border: 1px solid #d5f5e3;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  color: #1e8449;
  margin-bottom: 14px;
}
.settlement-empty {
  color: #7f8c8d;
  text-align: center;
  padding: 18px 0;
}
.settlement-section {
  margin-bottom: 14px;
}
.settlement-section h4 {
  margin: 0 0 8px;
  color: #34495e;
  font-size: 14px;
}
.settlement-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.settlement-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 0;
  border-bottom: 1px solid #f2f4f6;
  font-size: 14px;
}
.settlement-row:last-child {
  border-bottom: none;
}
.who {
  font-weight: bold;
  color: #2c3e50;
}
.arrow {
  color: #95a5a6;
}
.amount {
  margin-left: auto;
  font-weight: bold;
  color: #2c3e50;
  white-space: nowrap;
}
.amount.plus {
  color: #27ae60;
}
.deleted-note {
  background: #fff8e1;
  border: 1px solid #f1c40f;
  color: #7d6608;
  border-radius: 8px;
  padding: 9px 12px;
  font-size: 12px;
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
</style>
