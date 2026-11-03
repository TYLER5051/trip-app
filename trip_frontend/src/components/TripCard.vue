<script setup>
import { computed } from 'vue'

const props = defineProps({
  trip: { type: Object, required: true }
})

const packingPercent = computed(() => {
  const totalItems = props.trip.total_items || 0
  if (!totalItems) return 0
  return Math.round(((props.trip.packed_items || 0) / totalItems) * 100)
})
</script>

<template>
  <router-link :to="`/trips/${trip.id}`" class="trip-card-link">
    <div class="trip-card">
      <h2>{{ trip.title }}</h2>
      <p class="owner" v-if="trip.owner">
        Організатор: <strong>{{ trip.owner.username }}</strong>
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
.owner {
  color: #7f8c8d;
  font-size: 14px;
  margin: 5px 0;
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