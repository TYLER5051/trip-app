<script setup>
import { computed } from 'vue'
import UserAvatar from './UserAvatar.vue'

const props = defineProps({
  trip: { type: Object, required: true }
})

const packingPercent = computed(() => {
  const totalItems = props.trip.total_items || 0
  if (!totalItems) return 0
  return Math.round(((props.trip.packed_items || 0) / totalItems) * 100)
})

const formatDate = (d) => {
  if (!d) return null
  return new Date(d + 'T00:00:00').toLocaleDateString('uk-UA')
}

const tripDates = computed(() => {
  const s = formatDate(props.trip.start_date)
  const e = formatDate(props.trip.end_date)
  if (s && e) return `${s} – ${e}`
  return s || e || ''
})
</script>

<template>
  <router-link :to="`/trips/${trip.id}`" class="trip-card-link">
    <div class="trip-card">
      <h2>
        {{ trip.title }}
        <span v-if="trip.is_archived" class="archived-badge">Архівовано</span>
      </h2>
      <p v-if="tripDates" class="trip-dates">📅 {{ tripDates }}</p>
      <p class="owner" v-if="trip.owner">
        <span class="owner-inline">
          <UserAvatar
            :username="trip.owner.username"
            :color="trip.owner.avatar_color"
            :size="22"
          />
          Організатор: <strong>{{ trip.owner.username }}</strong>
        </span>
      </p>
      <p class="participants">
        Учасників: {{ trip.participants_count ?? 0 }}
      </p>
      <div class="packing-progress">
        <div class="progress-label">
          Зібрано {{ trip.packed_items ?? 0 }} із {{ trip.total_items ?? 0 }} речей ({{ packingPercent }}%)
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: packingPercent + '%' }"></div>
        </div>
      </div>
    </div>
  </router-link>
</template>

<style scoped>
.trip-card-link {
  text-decoration: none;
  color: inherit;
}
.trip-card {
  background: white;
  border: 1px solid #e1e8ed;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  height: 100%;
  box-sizing: border-box;
}
.trip-card h2 {
  margin: 0 0 10px 0;
  color: #34495e;
  font-size: 20px;
}
.trip-dates {
  color: #7f8c8d;
  font-size: 13px;
  margin: 5px 0;
}
.archived-badge {
  background-color: #f1c40f;
  color: #7d6608;
  font-size: 11px;
  font-weight: bold;
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: 6px;
  vertical-align: middle;
}
.owner {
  color: #7f8c8d;
  font-size: 14px;
  margin: 5px 0;
}
.owner-inline {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.participants {
  color: #7f8c8d;
  font-size: 14px;
  margin: 5px 0;
}
.packing-progress {
  margin-top: 15px;
}
.progress-label {
  font-size: 13px;
  color: #2980b9;
  font-weight: bold;
  margin-bottom: 6px;
}
.progress-track {
  background: #e1e8ed;
  border-radius: 8px;
  height: 8px;
  overflow: hidden;
}
.progress-fill {
  background: #27ae60;
  height: 100%;
  border-radius: 8px;
  transition: width 0.3s ease;
}
</style>