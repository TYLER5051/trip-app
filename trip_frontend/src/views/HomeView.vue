<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import api from '../services/api'

const trips = ref([])
const isLoading = ref(true)
const isLoadingMore = ref(false)
const errorMessage = ref('')
const currentUser = localStorage.getItem('username')

const searchInput = ref('')
const q = ref('')
const limit = 20
const total = ref(0)
const offset = ref(0)

let searchTimer = null

watch(searchInput, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    q.value = searchInput.value.trim()
    fetchTrips()
  }, 300)
})

const packingPercent = (trip) => {
  const totalItems = trip.total_items || 0
  if (!totalItems) return 0
  return Math.round(((trip.packed_items || 0) / totalItems) * 100)
}

const newTripTitle = ref('')
const isCreating = ref(false)
const createError = ref('')

const buildQuery = () => {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  params.set('offset', String(offset.value))
  if (q.value) params.set('q', q.value)
  return params.toString()
}

const fetchTrips = async (reset = true) => {
  if (reset) {
    offset.value = 0
    trips.value = []
    isLoading.value = true
  } else {
    isLoadingMore.value = true
  }
  errorMessage.value = ''

  try {
    const data = await api.get(`/trips/?${buildQuery()}`)
    trips.value = reset ? data.items : [...trips.value, ...data.items]
    total.value = data.total
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    isLoading.value = false
    isLoadingMore.value = false
  }
}

const loadMore = () => {
  offset.value += limit
  fetchTrips(false)
}

const hasMore = computed(() => trips.value.length < total.value)

const createTrip = async () => {
  if (!newTripTitle.value.trim()) return

  isCreating.value = true
  createError.value = ''

  try {
    await api.post('/trips/', { title: newTripTitle.value.trim() })
    newTripTitle.value = ''
    await fetchTrips()
  } catch (error) {
    createError.value = error.message
  } finally {
    isCreating.value = false
  }
}

onMounted(() => {
  fetchTrips()
})
</script>

<template>
  <div class="home-container">
    <div class="header-section">
      <h1>Доступні поїздки</h1>
      <div v-if="currentUser" class="welcome-user">
        Вітаю, <strong>{{ currentUser }}</strong>! 👋
      </div>
    </div>

    <div v-if="currentUser" class="create-trip-card">
      <h3>Створити нову поїздку</h3>
      <form @submit.prevent="createTrip" class="create-form">
        <input 
          type="text" 
          v-model="newTripTitle" 
          placeholder="Назва поїздки" 
          required
        />
        <button type="submit" :disabled="isCreating">
          {{ isCreating ? 'Створення...' : 'Створити' }}
        </button>
      </form>
      <div v-if="createError" class="error-message">{{ createError }}</div>
    </div>

    <div class="search-section">
      <input
        type="text"
        v-model="searchInput"
        placeholder="Пошук поїздок за назвою..."
        class="search-input"
      />
    </div>

    <div v-if="isLoading && trips.length === 0" class="loading">Завантаження даних...</div>
    <div v-else-if="errorMessage" class="error">{{ errorMessage }}</div>

    <template v-else>
      <div v-if="trips.length === 0 && q" class="empty">
        За пошуком нічого не знайдено.
      </div>

      <div v-else-if="total === 0" class="empty">
        Поки що немає жодної поїздки. Створи першу вище!
      </div>

      <template v-else>
        <div class="trip-grid">
          <router-link 
            v-for="trip in trips" 
            :key="trip.id" 
            :to="`/trips/${trip.id}`" 
            class="trip-card-link"
          >
            <div class="trip-card">
              <h2>{{ trip.title }}</h2>
              <p class="owner" v-if="trip.owner">
                Організатор: <strong>{{ trip.owner.username }}</strong>
              </p>
              <p class="participants">
                Учасників: {{ trip.participants ? trip.participants.length : 0 }}
              </p>
              <div class="packing-progress">
                <div class="progress-label">
                  Зібрано {{ trip.packed_items ?? 0 }} із {{ trip.total_items ?? 0 }} речей ({{ packingPercent(trip) }}%)
                </div>
                <div class="progress-track">
                  <div class="progress-fill" :style="{ width: packingPercent(trip) + '%' }"></div>
                </div>
              </div>
            </div>
          </router-link>
        </div>

        <button 
          v-if="hasMore" 
          class="load-more" 
          :disabled="isLoadingMore" 
          @click="loadMore"
        >
          {{ isLoadingMore ? 'Завантаження...' : 'Показати ще' }}
        </button>
      </template>
    </template>
  </div>
</template>

<style scoped>
.home-container {
  max-width: 900px;
  margin: 0 auto;
}
.trip-card-link { 
  text-decoration: none; 
  color: inherit; 
}
.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 25px;
}
h1 {
  color: #2c3e50;
  margin: 0;
}
.welcome-user {
  background: #e1f5fe;
  color: #0277bd;
  padding: 8px 15px;
  border-radius: 20px;
  font-size: 14px;
}
.search-section {
  margin-bottom: 20px;
}
.search-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid #ccc;
  border-radius: 8px;
  font-size: 15px;
  box-sizing: border-box;
}
.search-input:focus {
  outline: none;
  border-color: #42b883;
}
.load-more {
  display: block;
  margin: 25px auto 0;
  background-color: #42b883;
  color: white;
  border: none;
  padding: 10px 24px;
  border-radius: 20px;
  font-weight: bold;
  cursor: pointer;
}
.load-more:hover {
  background-color: #35495e;
}
.load-more:disabled {
  opacity: 0.6;
  cursor: default;
}
.create-trip-card {
  background: white;
  padding: 20px;
  border-radius: 10px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  margin-bottom: 30px;
}
.create-trip-card h3 {
  margin-top: 0;
  color: #34495e;
}
.create-form {
  display: flex;
  gap: 10px;
}
.create-form input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 5px;
  font-size: 15px;
}
.create-form button {
  background-color: #42b883;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 5px;
  font-weight: bold;
  cursor: pointer;
}
.create-form button:hover {
  background-color: #35495e;
}
.error-message {
  color: #e74c3c;
  margin-top: 10px;
  font-size: 14px;
}
.loading, .error, .empty {
  text-align: center;
  font-size: 18px;
  color: #666;
  margin-top: 40px;
}
.error {
  color: #e74c3c;
}
.trip-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}
.trip-card {
  background: white;
  border: 1px solid #e1e8ed;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
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