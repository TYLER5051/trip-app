<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import auth from '../stores/auth'
import TripCard from '../components/TripCard.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { AVATAR_COLORS } from '../utils/avatar'

const router = useRouter()

// Той самий формат, що й на бекенді: латинські/кириличні літери, цифри, дефіс, підкреслення.
const USERNAME_REGEX = /^[A-Za-zА-Яа-яІіЇїЄєҐґ0-9_-]+$/

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
const limit = 9
const offset = ref(0)

const newUsername = ref('')
const currentUsernamePassword = ref('')
const isChangingUsername = ref(false)
const usernameError = ref('')
const usernamePasswordError = ref('')
const usernameSuccess = ref('')

// Валідація на льоту — кнопка залишається вимкненою, поки логін не змінився,
// закороткий, містить недопустимі символи або не вказано поточний пароль.
const isUsernameSubmitDisabled = computed(() => {
  const name = newUsername.value.trim()
  if (isChangingUsername.value) return true
  if (name.length < 3) return true
  if (!USERNAME_REGEX.test(name)) return true
  if (name === profile.value?.username) return true
  return !currentUsernamePassword.value
})

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const isChangingPassword = ref(false)
const passwordError = ref('')
const passwordSuccess = ref('')

const avatarColorError = ref('')
const avatarColorSuccess = ref('')
const isSavingAvatarColor = ref(false)

const changeAvatarColor = async (color) => {
  avatarColorError.value = ''
  avatarColorSuccess.value = ''
  if (profile.value?.avatar_color === color) return

  isSavingAvatarColor.value = true
  try {
    await api.patch('/users/me', { avatar_color: color })
    avatarColorSuccess.value = 'Колір аватара збережено'
    await fetchProfile()
  } catch (error) {
    avatarColorError.value = error.message
  } finally {
    isSavingAvatarColor.value = false
  }
}

const totalItems = computed(() => profile.value?.total_items_count ?? 0)
const packedItems = computed(() => profile.value?.packed_items_count ?? 0)
const packedPercent = computed(() =>
  totalItems.value === 0 ? 0 : Math.round((packedItems.value / totalItems.value) * 100)
)

const hasMore = computed(() => trips.value.length < total.value)

const fetchProfile = async () => {
  try {
    profile.value = await api.get('/users/me')
  } catch (error) {
    profileError.value = error.message
  }
}

const assignedItems = ref([])
const isAssignedLoading = ref(true)
const assignedItemsError = ref('')
const isUnassigningId = ref(null)

// Агрегація по поїздках: бекенд і так повертає речі порядком (trip_id, id),
// тому достатньо розкласти в Map, не сортування.
const groupedByTrip = computed(() => {
  const groups = new Map()
  for (const item of assignedItems.value) {
    if (!groups.has(item.trip.id)) {
      groups.set(item.trip.id, { id: item.trip.id, title: item.trip.title, items: [] })
    }
    groups.get(item.trip.id).items.push(item)
  }
  return [...groups.values()]
})

const fetchAssignedItems = async () => {
  isAssignedLoading.value = true
  assignedItemsError.value = ''
  try {
    const data = await api.get('/users/me/assigned-items')
    assignedItems.value = data.items
  } catch (error) {
    assignedItemsError.value = error.message
  } finally {
    isAssignedLoading.value = false
  }
}

// Чекбокс «зняти з себе»: DELETE без user_id знімає позначку саме з мене.
const unassignItem = async (item) => {
  isUnassigningId.value = item.id
  try {
    await api.delete(`/items/${item.id}/assign`)
    assignedItems.value = assignedItems.value.filter(i => i.id !== item.id)
    await fetchProfile()
  } catch (error) {
    assignedItemsError.value = error.message
  } finally {
    isUnassigningId.value = null
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

const changeUsername = async () => {
  usernameError.value = ''
  usernamePasswordError.value = ''
  usernameSuccess.value = ''

  isChangingUsername.value = true
  try {
    const data = await api.patch('/users/me', {
      username: newUsername.value.trim(),
      current_password: currentUsernamePassword.value
    })
    // Бекенд видає новий токен після зміни username. Оновлюємо реактивний
    // стан автентифікації (auth store) — хедер та аватар оновлюються миттєво
    // без location.reload(). localStorage оновлюється всередині auth.setSession.
    auth.setSession(data.access_token, data.username)
    usernameSuccess.value = 'Логін успішно змінено'
    newUsername.value = ''
    currentUsernamePassword.value = ''
    await fetchProfile()
  } catch (error) {
    if (error.status === 400 && String(error.message).toLowerCase().includes('пароль')) {
      // «Введіть поточний пароль» або «Невірний поточний пароль» — під полем пароля.
      usernamePasswordError.value = error.message
    } else if (error.status === 400 && String(error.message).toLowerCase().includes('існує')) {
      usernameError.value = 'Цей логін вже зайнятий'
    } else {
      usernameError.value = error.message
    }
  } finally {
    isChangingUsername.value = false
  }
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
    const data = await api.patch('/users/me/password', {
      old_password: oldPassword.value,
      new_password: newPassword.value
    })
    // Бекенд при зміні пароля інвалідує всі старі токени (token_version += 1)
    // і повертає новий access_token — зберігаємо його, щоб поточна сесія не вилетіла.
    if (data.access_token) auth.setSession(data.access_token, data.username)
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

const deletePassword = ref('')
const isDeleting = ref(false)
const deleteError = ref('')

const deleteAccount = async () => {
  deleteError.value = ''

  if (!deletePassword.value) {
    deleteError.value = 'Введіть поточний пароль для підтвердження'
    return
  }

  if (!confirm(
    'УВАГА! Це незворотна дія. Усі ваші поїздки, де ви організатор, і ваші дані будуть видалені. Продовжити?'
  )) return

  isDeleting.value = true
  try {
    await api.delete('/users/me', { current_password: deletePassword.value })
    auth.clearSession()
    router.push('/login')
  } catch (error) {
    deleteError.value = error.message
  } finally {
    isDeleting.value = false
  }
}

onMounted(() => {
  fetchProfile()
  fetchTrips()
  fetchAssignedItems()
})
</script>

<template>
  <div class="profile-container">
    <div v-if="profileError" class="error">{{ profileError }}</div>

    <template v-else>
      <div class="profile-header">
        <UserAvatar :username="profile?.username" :color="profile?.avatar_color" :size="64" />
        <div class="profile-info">
          <h1>{{ profile?.username || 'Профіль' }}</h1>
          <p class="profile-subtitle">Твоя статистика подорожей</p>
        </div>
      </div>

      <div class="password-card">
        <h3>Колір аватара</h3>
        <div class="avatar-palette">
          <button
            v-for="color in AVATAR_COLORS"
            :key="color"
            class="color-swatch"
            :class="{ active: profile?.avatar_color === color }"
            :style="{ background: color }"
            :title="color"
            :aria-label="`Вибрати колір ${color}`"
            @click="changeAvatarColor(color)"
          ></button>
        </div>
        <div v-if="isSavingAvatarColor" class="palette-hint">Зберігаємо колір...</div>
        <div v-if="avatarColorError" class="error-message">{{ avatarColorError }}</div>
        <div v-if="avatarColorSuccess" class="success-message">{{ avatarColorSuccess }}</div>
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

      <div class="packing-card">
        <div class="packing-head">
          <strong>Зібрано {{ packedItems }} із {{ totalItems }} речей за всіма поїздками</strong>
          <span class="packing-percent">{{ packedPercent }}%</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: packedPercent + '%' }"></div>
        </div>
      </div>

      <div class="assigned-card">
        <div class="card-head">
          <h3>Мої доручені речі</h3>
          <span v-if="assignedItems.length" class="assigned-count">{{ assignedItems.length }}</span>
        </div>

        <div v-if="isAssignedLoading" class="loading small">Завантаження...</div>
        <div v-else-if="assignedItemsError" class="error-message">{{ assignedItemsError }}</div>
        <div v-else-if="assignedItems.length === 0" class="assigned-empty">
          У тебе поки немає доручених речей.
        </div>

        <template v-else>
          <div v-for="group in groupedByTrip" :key="group.id" class="assigned-group">
            <router-link :to="`/trips/${group.id}`" class="assigned-trip-title">{{ group.title }}</router-link>
            <ul class="assigned-list">
              <li v-for="item in group.items" :key="item.id" class="assigned-item">
                <label class="assigned-check" :title="`Зняти з себе «${item.name}»`">
                  <input
                    type="checkbox"
                    :checked="true"
                    :disabled="isUnassigningId === item.id"
                    @change="unassignItem(item)"
                  />
                  <span class="assigned-item-name">{{ item.name }}</span>
                </label>
                <span v-if="item.is_critical" class="critical-badge" title="Важлива">🔥</span>
                <span v-if="item.category" class="category-badge">{{ item.category.name }}</span>
                <span v-if="item.quantity > 1" class="qty-badge">×{{ item.quantity }}</span>
                <span v-if="isUnassigningId === item.id" class="unassign-spinner">Знімаємо...</span>
              </li>
            </ul>
          </div>
        </template>
      </div>

      <div class="password-card">
        <h3>Зміна логіна</h3>
        <form @submit.prevent="changeUsername" class="password-form">
          <div class="form-group">
            <label>Новий логін</label>
            <input
              type="text"
              v-model="newUsername"
              placeholder="Мінімум 3 символи, без пробілів"
              minlength="3"
              maxlength="30"
            />

            <div v-if="usernameError" class="error-message">{{ usernameError }}</div>
            <div v-if="newUsername.trim() && !USERNAME_REGEX.test(newUsername.trim())" class="error-message">
              Лише літери, цифри, дефіс та підкреслення
            </div>
          </div>

          <div class="form-group">
            <label>Поточний пароль</label>
            <input
              type="password"
              v-model="currentUsernamePassword"
              placeholder="Для підтвердження зміни"
            />

            <div v-if="usernamePasswordError" class="error-message">{{ usernamePasswordError }}</div>
          </div>

          <div class="form-group">
            <div v-if="usernameSuccess" class="success-message">{{ usernameSuccess }}</div>
          </div>

          <div v-if="!isUsernameSubmitDisabled" class="form-hint">
            Новий логін одразу відображатиметься у ваших поїздках та призначених речах.
          </div>

          <button type="submit" :disabled="isUsernameSubmitDisabled" class="password-btn">
            {{ isChangingUsername ? 'Зберігаємо...' : 'Змінити логін' }}
          </button>
        </form>
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

      <div class="password-card danger-card">
        <h3>Видалити акаунт</h3>
        <p class="palette-hint">
          Видалення незворотне: ваші поїздки, де ви організатор, і ваші дані будуть стерті.
        </p>
        <form @submit.prevent="deleteAccount" class="password-form">
          <div class="form-group">
            <label>Поточний пароль</label>
            <input
              type="password"
              v-model="deletePassword"
              placeholder="Для підтвердження видалення"
            />
            <div v-if="deleteError" class="error-message">{{ deleteError }}</div>
          </div>
          <button type="submit" :disabled="isDeleting || !deletePassword" class="password-btn danger-btn">
            {{ isDeleting ? 'Видаляємо...' : 'Видалити акаунт' }}
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
.avatar-palette {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}
.color-swatch {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 3px solid transparent;
  cursor: pointer;
  transition: transform 0.15s ease, border-color 0.15s ease;
  padding: 0;
}
.color-swatch:hover {
  transform: scale(1.12);
}
.color-swatch.active {
  border-color: #2c3e50;
  transform: scale(1.1);
  box-shadow: 0 0 0 2px #fff inset;
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
.packing-card {
  background: white;
  border-radius: 10px;
  padding: 18px 24px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  margin-bottom: 30px;
}
.packing-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  color: #2c3e50;
  font-size: 15px;
}
.packing-percent {
  color: #42b883;
  font-weight: bold;
}
.progress-bar {
  background: #ecf0f1;
  border-radius: 12px;
  height: 12px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #42b883, #27ae60);
  border-radius: 12px;
  transition: width 0.3s ease;
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
.danger-card {
  border: 1px solid #f5c6cb;
  border-left: 4px solid #e74c3c;
}
.danger-btn {
  background-color: #e74c3c;
}
.danger-btn:hover {
  background-color: #c0392b;
}
.danger-btn:disabled {
  background-color: #98a6ad;
}
.error-message {
  color: #e74c3c;
  font-size: 14px;
}
.success-message {
  color: #27ae60;
  font-size: 14px;
}
.form-hint {
  color: #7f8c8d;
  font-size: 13px;
  line-height: 1.4;
}
.palette-hint {
  color: #7f8c8d;
  font-size: 13px;
  margin-top: 4px;
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
.assigned-card {
  background: white;
  border-radius: 10px;
  padding: 20px 24px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  margin-bottom: 30px;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 15px;
}
.card-head h3 {
  margin: 0;
  color: #34495e;
}
.assigned-count {
  background: #42b883;
  color: white;
  font-weight: bold;
  font-size: 13px;
  padding: 2px 10px;
  border-radius: 12px;
}
.assigned-empty {
  color: #7f8c8d;
  font-size: 14px;
  padding: 10px 0;
}
.loading.small {
  margin: 0;
  font-size: 14px;
}
.assigned-group {
  margin-bottom: 18px;
}
.assigned-group:last-child {
  margin-bottom: 0;
}
.assigned-trip-title {
  display: inline-block;
  color: #2c3e50;
  font-size: 15px;
  font-weight: bold;
  text-decoration: none;
  margin-bottom: 8px;
}
.assigned-trip-title:hover {
  color: #42b883;
}
.assigned-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.assigned-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  margin-bottom: 6px;
}
.assigned-item:hover {
  background: #f0f4f7;
}
.assigned-check {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  flex: 1;
  min-width: 0;
}
.assigned-check input[type='checkbox'] {
  width: 17px;
  height: 17px;
  cursor: pointer;
  accent-color: #27ae60;
}
.assigned-item-name {
  font-size: 15px;
  color: #2c3e50;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.category-badge {
  background: #eef2f5;
  color: #546e7a;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
  white-space: nowrap;
}
.qty-badge {
  background: #e8f5e9;
  color: #27ae60;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: bold;
  white-space: nowrap;
}
.critical-badge {
  font-size: 14px;
  background: none;
  border: none;
  padding: 0;
}
.unassign-spinner {
  color: #7f8c8d;
  font-size: 12px;
  white-space: nowrap;
}
</style>