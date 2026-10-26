<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import api from '../services/api'
import TripHeader from './TripHeader.vue'
import TripParticipants from './TripParticipants.vue'
import TripItemForm from './TripItemForm.vue'
import TripItemList from './TripItemList.vue'

const route = useRoute()
const router = useRouter()
const tripId = route.params.id

const trip = ref(null)
const categories = ref([])
const isLoading = ref(true)
const errorMessage = ref('')

// Отримуємо поточного користувача для перевірки прав
const currentUser = localStorage.getItem('username')


// Завантаження даних поїздки та категорій
const fetchTripData = async () => {
  try {
    const [tripData, catsData] = await Promise.all([
      api.get(`/trips/${tripId}`),
      api.get(`/trips/${tripId}/categories/`)
    ])
    trip.value = tripData
    categories.value = catsData
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    isLoading.value = false
  }
}

// Групування речей за категоріями
const groupedItems = computed(() => {
  if (!trip.value || !trip.value.items) return {}

  const groups = {}
  // Спочатку кладемо всі категорії, щоб навіть порожні були видимі
  // (інакше порожню категорію неможливо було б видалити з інтерфейсу)
  categories.value.forEach(cat => {
    groups[cat.name] = []
  })

  trip.value.items.forEach(item => {
    const categoryObj = item.category || categories.value.find(c => c.id == item.category_id)
    const categoryName = categoryObj ? categoryObj.name : 'Інше'

    if (!groups[categoryName]) {
      groups[categoryName] = []
    }
    groups[categoryName].push(item)
  })

  // Важливі речі — першими в своїй категорії, далі за порядком створення
  Object.values(groups).forEach(list => {
    list.sort((a, b) => (b.is_critical === true) - (a.is_critical === true) || a.id - b.id)
  })

  return groups
})

const isParticipant = computed(() => {
  if (!trip.value || !trip.value.participants) return false
  return trip.value.participants.some(p => p.username === currentUser)
})

const packingPercent = computed(() => {
  const total = trip.value?.total_items || 0
  if (!total) return 0
  return Math.round(((trip.value?.packed_items || 0) / total) * 100)
})

// Видалення учасника (ТІЛЬКИ ДЛЯ ОРГАНІЗАТОРА)
const removeParticipant = async (participantId) => {
  const participant = trip.value?.participants?.find(p => p.id === participantId)
  const freedCount = (trip.value?.items || []).filter(item =>
    item.assigned_users && item.assigned_users.some(u => u.id === participantId)
  ).length

  const who = participant ? `«${participant.username}»` : `ID ${participantId}`
  if (!confirm(`Видалити учасника ${who}? Його взяті речі (${freedCount}) стануть вільними.`)) return

  try {
    await api.delete(`/trips/${tripId}/participants/${participantId}`)
    await fetchTripData()
    toast.success(freedCount > 0 ? `Речі учасника звільнено: ${freedCount} шт.` : 'Учасника видалено.')
  } catch (error) {
    toast.error(error.message)
  }
}

// Приєднання до поїздки
const joinTrip = async () => {
  try {
    await api.post(`/trips/${tripId}/join`)
    await fetchTripData()
  } catch (error) {
    toast.error(error.message)
  }
}

// Вихід з поїздки (ДЛЯ УЧАСНИКА)
const leaveTrip = async () => {
  if (!confirm('Ти дійсно хочеш вийти з цієї поїздки? Всі твої спаковані речі стануть вільними.')) return

  try {
    await api.delete(`/trips/${tripId}/leave`)

    // Після успішного виходу кидаємо користувача на головну сторінку
    router.push('/')
  } catch (error) {
    toast.error(error.message)
  }
}


const createCategory = async (categoryName) => {
  try {
    await api.post(`/trips/${tripId}/categories/`, { name: categoryName })

    await fetchTripData()
    toast.success("Категорію успішно створено.")
  } catch (error) {
    toast.error(error.message)
  }
}


// Перейменування категорії (тільки організатор або автор категорії)
const renameCategory = async ({ id, name }) => {
  if (!name || name.trim().length < 2) {
    toast.error('Назва категорії має містити щонайменше 2 символи')
    return
  }

  try {
    await api.patch(`/trips/${tripId}/categories/${id}`, { name: name.trim() })

    await fetchTripData()
    toast.success('Категорію перейменовано.')
  } catch (error) {
    toast.error(error.message)
  }
}

// Видалення категорії (тільки організатор або автор) — речі переносяться в "Інше"
const deleteCategory = async (category) => {
  const itemCount = trip.value.items
    ? trip.value.items.filter(i => i.category_id === category.id).length
    : 0

  const message = itemCount > 0
    ? `Видалити категорію "${category.name}"? Речі (${itemCount}) буде перенесено до "Інше".`
    : `Видалити категорію "${category.name}"?`

  if (!confirm(message)) return

  try {
    await api.delete(`/trips/${tripId}/categories/${category.id}`)

    await fetchTripData()
    toast.success('Категорію видалено.')
  } catch (error) {
    toast.error(error.message)
  }
}

const addItem = async (payload) => {
  try {
    await api.post('/items/', {
      name: payload.name,
      trip_id: Number(tripId),
      category_id: Number(payload.categoryId),
      quantity: payload.quantity ?? 1,
      note: payload.note || null,
      is_critical: payload.is_critical ?? false
    })

    await fetchTripData()
    toast.success("Річ додано до списку.")
  } catch (error) {
    toast.error(error.message)
  }
}

// Взяття речі через чекбокс: кожен учасник «бере» свій слот (поки є місця = quantity)
const toggleItemAssignment = async (item) => {
  const assignedByMe = item.assigned_users && item.assigned_users.some(a => a.username === currentUser)

  try {
    if (assignedByMe) {
      await api.delete(`/items/${item.id}/assign`)
    } else {
      await api.post(`/items/${item.id}/assign`)
    }
    await fetchTripData()
  } catch (error) {
    toast.error(error.message)
  }
}

// Зміна кількості після створення (тільки автор або організатор)
const updateItemQuantity = async ({ id, quantity }) => {
  const qty = Number(quantity)
  if (!qty || qty < 1) {
    toast.error('Кількість має бути не менше 1')
    return
  }

  try {
    await api.patch(`/items/${id}`, { quantity: qty })
    await fetchTripData()
    toast.success('Кількість оновлено.')
  } catch (error) {
    toast.error(error.message)
  }
}

// Зняти мітку «Важлива» (тільки автор або організатор) — після цього річ можна видалити
const unmarkCritical = async (item) => {
  if (!confirm(`Зняти мітку «Важлива» з речі "${item.name}"? Після цього її можна буде видалити.`)) return

  try {
    await api.patch(`/items/${item.id}`, { is_critical: false })
    await fetchTripData()
    toast.success('Мітку «Важлива» знято.')
  } catch (error) {
    toast.error(error.message)
  }
}

// Перейменування речі (тільки організатор або автор речі)
const renameItem = async ({ id, name }) => {
  if (!name || name.trim().length < 2) {
    toast.error('Назва речі має містити щонайменше 2 символи')
    return
  }

  try {
    await api.patch(`/items/${id}`, { name: name.trim() })

    await fetchTripData()
    toast.success('Річ перейменовано.')
  } catch (error) {
    toast.error(error.message)
  }
}

// Видалення речі (тільки організатор або автор речі)
const deleteItem = async (itemId) => {
  if (!confirm('Видалити цю річ зі списку?')) return

  try {
    await api.delete(`/items/${itemId}`)
    await fetchTripData()
    toast.success('Річ видалено.')
  } catch (error) {
    toast.error(error.message)
  }
}

// Видалення поїздки (ТІЛЬКИ ДЛЯ ОРГАНІЗАТОРА)
const deleteTrip = async () => {
  if (!confirm('УВАГА! Ти дійсно хочеш видалити цю поїздку назавжди?')) return

  try {
    await api.delete(`/trips/${tripId}`)
    router.push('/')
  } catch (error) {
    toast.error(error.message)
  }
}

// Перейменування поїздки (тільки організатор)
const renameTrip = async (newTitle) => {
  if (!newTitle || newTitle.trim().length < 3) {
    toast.error('Назва поїздки має містити щонайменше 3 символи')
    return
  }

  try {
    await api.patch(`/trips/${tripId}`, { title: newTitle.trim() })

    await fetchTripData()
    toast.success('Поїздку перейменовано.')
  } catch (error) {
    toast.error(error.message)
  }
}

onMounted(() => {
  fetchTripData()
})

</script>

<template>
  <div class="trip-detail-container">
    <div v-if="isLoading" class="loading">Завантаження поїздки...</div>
    <div v-else-if="errorMessage" class="error">{{ errorMessage }}</div>

    <div v-else-if="trip">
      
      <!-- header -->
      <TripHeader 
        :trip="trip" 
        :currentUser="currentUser" 
        :isParticipant="isParticipant"
        @join="joinTrip"
        @leave="leaveTrip"
        @delete="deleteTrip"
        @rename="renameTrip"
      />

      <div class="packing-progress-card">
        <div class="progress-label">
          Зібрано {{ trip.packed_items ?? 0 }} із {{ trip.total_items ?? 0 }} речей ({{ packingPercent }}%)
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: packingPercent + '%' }"></div>
        </div>
      </div>
      
      <!-- учасники -->
      <TripParticipants 
        :participants="trip.participants"
        :ownerUsername="trip.owner?.username"
        :currentUser="currentUser"
        @remove="removeParticipant"
      />
      
      <!-- додавання речей-->
      <TripItemForm 
        :categories="categories" 
        @add-item="addItem" 
        @create-category="createCategory" 
      />
      
      <!-- список речей -->
      <TripItemList 
        :groupedItems="groupedItems"
        :categories="categories"
        :currentUser="currentUser"
        :ownerUsername="trip.owner?.username"
        @toggle="toggleItemAssignment"
        @delete="deleteItem"
        @rename="renameItem"
        @update-quantity="updateItemQuantity"
        @unmark-critical="unmarkCritical"
        @rename-category="renameCategory"
        @delete-category="deleteCategory"
      />
    </div>
    
  </div>
</template>

<style scoped>
.trip-detail-container {
  max-width: 800px;
  margin: 0 auto;
}
.loading, .error {
  text-align: center;
  color: #666;
  margin-top: 20px;
}
.packing-progress-card {
  background: white;
  padding: 15px 20px;
  border-radius: 10px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  margin-bottom: 20px;
}
.progress-label {
  font-size: 14px;
  color: #2980b9;
  font-weight: bold;
  margin-bottom: 8px;
}
.progress-track {
  background: #e1e8ed;
  border-radius: 8px;
  height: 10px;
  overflow: hidden;
}
.progress-fill {
  background: #27ae60;
  height: 100%;
  border-radius: 8px;
  transition: width 0.3s ease;
}
</style>