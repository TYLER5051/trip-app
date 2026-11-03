<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../services/api'
import TripCard from '../components/TripCard.vue'

const profile = ref(null)
const profileError = ref('')

const tabs = [
  { key: 'owned', label: 'Я організовую' },
  { key: 'joined', label: 'Учасник' }
]
const activeTab = ref('owned')

const trips = ref([])
const total = ref(0)
const isLoading = ref(true)
const isLoadingMore = ref(false)
const errorMessage = ref('')
const limit = 20
const offset = ref(0)

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const isChangingPassword = ref(false)
const passwordError = ref('')
const passwordSuccess = ref('')

const avatarLetter = computed(() => (profile.value?.username?.[0] || '?').toUpperCase())

const hasMore = computed(() => trips.value.length < total.value)

const fetchProfile = async () => {
  try {
    profile.value = await api.get('/users/me')
  } catch (error) {
    profileError.value = error.message
  }
}

const buildQuery = () => {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset.value),
    role: activeTab.value
  })
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

const switchTab = (key) => {
  if (activeTab.value === key) return
  activeTab.value = key
  fetchTrips()
}

const loadMore = () => {
  offset.value += limit
  fetchTrips(false)
}

const changePassword = async () => {
  passwordError.value = ''
  passwordSuccess.value = ''

  if (!oldPassword.value) {
    passwordError.value = 'Введіть поточний пароль'
    return
  }
  if (newPassword.value.length < 8) {
    passwordError.value = 'Новий пароль має містити щонайменше 8 символів'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = 'Паролі не співпадають'
    return
  }

  isChangingPassword.value = true
  try {
    await api.patch('/users/me/password', {
      old_password: oldPassword.value,
      new_password: newPassword.value
    })
    passwordSuccess.value = 'Пароль успішно змінено'
    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (error) {
    passwordError.value = error.message
  } finally {
    isChangingPassword.value = false
  }
}

onMounted(() => {
  fetchProfile()
  fetchTrips()
})
</script>

<template>
  <div class="profile-container">
    <div v-if="profileError" class="error">{{ profileError }}</div>

    <template v-else>
      <div class="profile-header">
        <div class="avatar">{{ avatarLetter }}</div>
        <div class="profile-info">
          <h1>{{ profile?.username || 'Профіль' }}</h1>
          <p class="profile-subtitle">Твоя статистика подорожей</p>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-number">{{ profile?.owned_trips_count ?? 0 }}</div>
          <div class="stat-label">Створено поїздок</div>
        </div>
        <div class="stat-card">
          <div class="stat-number">{{ profile?.participating_trips_count ?? 0 }}</div>
          <div class="stat-label">Участь у поїздках</div>
        </div>
        <div class="stat-card">
          <div class="stat-number">{{ profile?.assigned_items_count ?? 0 }}</div>
          <div class="stat-label">Доручених речей</div>
        </div>
      </div>

      <div class="password-card">
        <h3>Зміна пароля</h3>
        <form @submit.prevent="changePassword" class="password-form">
          <div class="form-group">
            <label>Поточний пароль</label>
            <input type="password" v-model="oldPassword" placeholder="Введи поточний пароль" />
          </div>
          <div class="form-group">
            <label>Новий пароль</label>
            <input type="password" v-model="newPassword" placeholder="Мінімум 8 символів" minlength="8" />
          </div>
          <div class="form-group">
            <label>Повтори новий пароль</label>
            <input type="password" v-model="confirmPassword" placeholder="Повтори новий пароль" minlength="8" />
          </div>

          <div v-if="passwordError" class="error-message">{{ passwordError }}</div>
          <div v-if="passwordSuccess" class="success-message">{{ passwordSuccess }}</div>

          <button type="submit" :disabled="isChangingPassword" class="password-btn">
            {{ isChangingPassword ? 'Зберігаємо...' : 'Змінити пароль' }}
          </button>
        </form>
      </div>

      <div class="trips-section">
        <div class="tabs">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="tab-btn"
            :class="{ active: activeTab === tab.key }"
            @click="switchTab(tab.key)"
          >
            {{ tab.label }}
          </button>
        </div>

        <div v-if="isLoading && trips.length === 0" class="loading">Завантаження даних...</div>
        <div v-else-if="errorMessage" class="error">{{ errorMessage }}</div>

        <template v-else>
          <div v-if="total === 0" class="empty">
            {{ activeTab === 'owned' ? 'Ти ще не створив(ла) жодної поїздки.' : 'Ти ще не приєднався(лася) до чужих поїздок.' }}
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
  </div>
</template>

<style scoped>
.profile-container {
  max-width: 900px;
  margin: 0 auto;
}
.profile-header {
  display: flex;
  align-items: center;
  gap: 20px;
  background: white;
  border-radius: 12px;
  padding: 25px 30px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  margin-bottom: 20px;
}
.avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #42b883;
  color: white;
  font-size: 28px;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
}
.profile-info h1 {
  margin: 0;
  color: #2c3e50;
}
.profile-subtitle {
  margin: 5px 0 0;
  color: #7f8c8d;
  font-size: 14px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}
.stat-card {
  background: white;
  border-radius: 10px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}
.stat-number {
  font-size: 30px;
  font-weight: bold;
  color: #2c3e50;
}
.stat-label {
  margin-top: 8px;
  color: #7f8c8d;
  font-size: 14px;
}
.password-card {
  background: white;
  border-radius: 10px;
  padding: 20px 24px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  margin-bottom: 30px;
}
.password-card h3 {
  margin: 0 0 15px 0;
  color: #34495e;
}
.password-form {
  display: flex;
  flex-direction: column;
  gap: 15px;
  max-width: 420px;
}
.password-form .form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.password-form label {
  color: #34495e;
  font-weight: bold;
  font-size: 14px;
}
.password-form input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 5px;
  font-size: 15px;
}
.password-form input:focus {
  outline: none;
  border-color: #42b883;
}
.password-btn {
  align-self: flex-start;
  background-color: #42b883;
  color: white;
  border: none;
  padding: 10px 22px;
  border-radius: 20px;
  font-weight: bold;
  font-size: 14px;
  cursor: pointer;
}
.password-btn:hover {
  background-color: #35495e;
}
.password-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.error-message {
  color: #e74c3c;
  font-size: 14px;
}
.success-message {
  color: #27ae60;
  font-size: 14px;
}
.tabs {
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
.trip-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
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
.loading, .error, .empty {
  text-align: center;
  font-size: 18px;
  color: #666;
  margin-top: 40px;
}
.error {
  color: #e74c3c;
}
</style>