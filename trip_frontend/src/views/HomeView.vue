<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import api from '../services/api'
import TripCard from '../components/TripCard.vue'

const trips = ref([])
const isLoading = ref(true)
const isLoadingMore = ref(false)
const errorMessage = ref('')
const currentUser = localStorage.getItem('username')

const searchInput = ref('')
const q = ref('')
const limit = 9
const total = ref(0)
const offset = ref(0)

// Вкладки «Активні» / «Архів»
const activeTab = ref('active')

const switchTab = (tab) => {
  if (activeTab.value === tab) return
  activeTab.value = tab
  fetchTrips()
}

let searchTimer = null

watch(searchInput, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    q.value = searchInput.value.trim()
    fetchTrips()
  }, 300)
})

const newTripTitle = ref('')
const newTripStart = ref('')
const newTripEnd = ref('')
const isCreating = ref(false)
const createError = ref('')

const buildQuery = () => {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  params.set('offset', String(offset.value))
  if (q.value) params.set('q', q.value)
  if (activeTab.value === 'archived') params.set('role', 'archived')
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

  // Ввід менше ніж 3 символи (напр. через Enter у формі) — не слати запит, а пояснити.
  if (newTripTitle.value.trim().length < 3) {
    createError.value = 'Назва поїздки має містити щонайменше 3 символи'
    return
  }

  isCreating.value = true
  createError.value = ''

  try {
    await api.post('/trips/', {
      title: newTripTitle.value.trim(),
      start_date: newTripStart.value || null,
      end_date: newTripEnd.value || null
    })
    newTripTitle.value = ''
    newTripStart.value = ''
    newTripEnd.value = ''
    await fetchTrips()
  } catch (error) {
    createError.value = error.message
  } finally {
    isCreating.value = false
  }
}

// Клієнтська перевірка: не даємо відправляти явно закоротку назву (бекенд вимагає >= 3).
const canCreateTrip = computed(() => newTripTitle.value.trim().length >= 3 && !isCreating.value)

// Підказка під час вводу: щось введено, але менше ніж 3 символи.
const titleTooShort = computed(() => {
  const len = newTripTitle.value.trim().length
  return len > 0 && len < 3
})

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

    <div class="tab-bar">
      <button class="tab-btn" :class="{ active: activeTab === 'active' }" @click="switchTab('active')">Активні</button>
      <button class="tab-btn" :class="{ active: activeTab === 'archived' }" @click="switchTab('archived')">Архів</button>
    </div>

    <div v-if="currentUser && activeTab === 'active'" class="create-trip-card">
      <h3>Створити нову поїздку</h3>
      <form @submit.prevent="createTrip" class="create-form">
        <input 
          type="text" 
          v-model="newTripTitle" 
          placeholder="Назва поїздки" 
          required
        />
        <label class="create-date">
          <span>Початок</span>
          <input type="date" v-model="newTripStart" />
        </label>
        <label class="create-date">
          <span>Кінець</span>
          <input type="date" v-model="newTripEnd" />
        </label>
        <button type="submit" :disabled="!canCreateTrip">
          {{ isCreating ? 'Створення...' : 'Створити' }}
        </button>
      </form>
      <div v-if="titleTooShort" class="error-message hint-message">
        Назва поїздки має містити щонайменше 3 символи
      </div>
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
        {{ activeTab === 'archived' ? 'Архів порожній.' : 'Поки що немає жодної поїздки. Створи першу вище!' }}
      </div>

      <template v-else>
        <div class="trip-grid">
          <TripCard v-for="trip in trips" :key="trip.id" :trip="trip" />
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
.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 25px;
}
.tab-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}
.tab-btn {
  background: white;
  border: 1px solid #e1e8ed;
  color: #34495e;
  padding: 10px 20px;
  border-radius: 20px;
  font-size: 15px;
  font-weight: bold;
  cursor: pointer;
}
.tab-btn.active {
  background: #42b883;
  border-color: #42b883;
  color: white;
}
.tab-btn:hover:not(.active) {
  border-color: #42b883;
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
  flex-wrap: wrap;
  gap: 10px;
}
.create-form > input[type="text"] {
  flex: 1;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 5px;
  font-size: 15px;
  min-width: 200px;
}
.create-date {
  display: flex;
  flex-direction: column;
  font-size: 12px;
  color: #7f8c8d;
  gap: 2px;
}
.create-date input[type="date"] {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 5px;
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
.create-form button:hover:not(:disabled) {
  background-color: #35495e;
}
.create-form button:disabled {
  background-color: #98a6ad;
  cursor: default;
}
.hint-message {
  margin-top: 6px;
  font-size: 13px;
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
</style>