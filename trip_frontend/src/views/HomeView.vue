<script setup>
import { ref, onMounted } from 'vue'

const trips = ref([])
const isLoading = ref(true)
const errorMessage = ref('')
const currentUser = localStorage.getItem('username')

const newTripTitle = ref('')
const isCreating = ref(false)
const createError = ref('')

const fetchTrips = async () => {
  const token = localStorage.getItem('access_token')
  try {
    const res = await fetch('http://localhost:8000/trips/', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    
    if (!res.ok) throw new Error('Не вдалося завантажити поїздки')
    trips.value = await res.json()
  } catch (error) {
    console.error(error.message)
  } finally {
    isLoading.value = false 
  }
}

const createTrip = async () => {
  if (!newTripTitle.value.trim()) return

  isCreating.value = true
  createError.value = ''
  
  const token = localStorage.getItem('access_token')

  try {
    const response = await fetch('http://localhost:8000/trips/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ title: newTripTitle.value })
    })

    if (!response.ok) {
      throw new Error('Не вдалося створити поїздку. Можливо, токен закінчився.')
    }

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

    <div v-if="isLoading" class="loading">Завантаження даних...</div>
    <div v-else-if="errorMessage" class="error">{{ errorMessage }}</div>
    
    <div v-else-if="trips.length === 0" class="empty">
      Поки що немає жодної поїздки. Створи першу вище!
    </div>

    <div v-else class="trip-grid">
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
          <div class="items-preview">
            Речей у списку: {{ trip.items ? trip.items.length : 0 }}
          </div>
        </div>
      </router-link>
    </div>
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
.items-preview {
  margin-top: 15px;
  font-size: 14px;
  color: #2980b9;
  font-weight: bold;
}
</style>