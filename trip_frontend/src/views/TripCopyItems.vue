<script setup>
defineProps({
  trips: { type: Array, required: true },
  isLoading: { type: Boolean, default: false }
})
defineEmits(['close', 'copy'])
</script>

<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="copy-modal">
      <h3>Наслідувати речі з іншої поїздки</h3>
      <p class="hint">
        Оберіть поїздку — її категорії та речі буде скопійовано у поточну.
        Дублікати за назвою буде пропущено.
      </p>

      <div v-if="isLoading" class="modal-status">Завантаження поїздок...</div>
      <div v-else-if="trips.length === 0" class="modal-status">
        Поки немає інших поїздок із речами, які можна наслідувати.
        Додайте речі в іншу поїздку (створіть свою чи приєднайтесь за інвайтом) —
        і тоді вони з'являться тут і скопіюються в цю поїздку одним кліком.
      </div>

      <ul v-else class="trip-list">
        <li v-for="t in trips" :key="t.id" class="trip-row">
          <div class="trip-info">
            <div class="trip-title">{{ t.title }}</div>
            <div class="trip-meta">
              {{ t.total_items }} речей
              <template v-if="t.start_date">· {{ t.start_date }}{{ t.end_date ? ' — ' + t.end_date : '' }}</template>
              <span v-if="t.is_archived" class="archived-badge">архів</span>
            </div>
          </div>
          <button class="copy-btn" @click="$emit('copy', t.id)">Наслідувати</button>
        </li>
      </ul>

      <button class="close-btn" @click="$emit('close')">Закрити</button>
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
.copy-modal {
  background: white;
  border-radius: 12px;
  padding: 25px;
  width: min(520px, 92vw);
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}
.copy-modal h3 {
  margin: 0 0 8px;
  color: #2c3e50;
}
.hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: #7f8c8d;
}
.modal-status {
  padding: 20px;
  text-align: center;
  color: #7f8c8d;
}
.trip-list {
  list-style: none;
  margin: 0 0 18px;
  padding: 0;
  max-height: 45vh;
  overflow-y: auto;
}
.trip-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #e1e8ed;
  border-radius: 8px;
  margin-bottom: 8px;
}
.trip-title {
  font-weight: bold;
  color: #2c3e50;
}
.trip-meta {
  font-size: 12px;
  color: #7f8c8d;
  margin-top: 2px;
}
.archived-badge {
  background: #f1f2f6;
  color: #7f8c8d;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 11px;
  margin-left: 4px;
}
.copy-btn {
  background-color: #42b883;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
  white-space: nowrap;
}
.copy-btn:hover {
  background-color: #35495e;
}
.close-btn {
  width: 100%;
  background: #ecf0f1;
  color: #34495e;
  border: none;
  padding: 9px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
.close-btn:hover {
  background: #dde3e7;
}
</style>