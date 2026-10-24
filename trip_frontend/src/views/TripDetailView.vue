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

  return groups
})

const isParticipant = computed(() => {
  if (!trip.value || !trip.value.participants) return false
  return trip.value.participants.some(p => p.username === currentUser)
})

// Видалення учасника (ТІЛЬКИ ДЛЯ ОРГАНІЗАТОРА)
const removeParticipant = async (participantId) => {
  if (!confirm('Видалити цього учасника з поїздки?')) return

  try {
    await api.delete(`/trips/${tripId}/participants/${participantId}`)
    await fetchTripData()
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
      category_id: Number(payload.categoryId)
    })

    await fetchTripData()
    toast.success("Річ додано до списку.")
  } catch (error) {
    toast.error(error.message)
  }
}

// Бронювання речі через чекбокс
const toggleItemAssignment = async (item) => {
  const isAssigned = !!item.assigned_user

  try {
    // Відправляємо тільки статус галочки (true або false)
    await api.patch(`/items/${item.id}`, { is_packed: !isAssigned })
    await fetchTripData()
  } catch (error) {
    toast.error(error.message)
    console.error(error)
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
      />
      
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
</style>