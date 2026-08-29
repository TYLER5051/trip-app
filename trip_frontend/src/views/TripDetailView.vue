<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
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
  const token = localStorage.getItem('access_token') // 1. Дістаємо токен

  try {
    const [tripRes, catRes] = await Promise.all([
      // Запит за поїздкою (тут токен вже є)
      fetch(`${import.meta.env.VITE_API_URL}/trips/${tripId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }),
      // ДОДАЄМО ТОКЕН СЮДИ ДЛЯ КАТЕГОРІЙ!
      fetch(`${import.meta.env.VITE_API_URL}/trips/${tripId}/categories/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
    ])

    if (!tripRes.ok) {
      if (tripRes.status === 401) throw new Error('Помилка авторизації. Увійдіть знову.')
      if (tripRes.status === 403) throw new Error('У вас немає доступу до цієї поїздки.')
      if (!catRes.ok) throw new Error('Не вдалося завантажити категорії')
      throw new Error('Поїздку не знайдено')
    }
    
    trip.value = await tripRes.json()
    categories.value = await catRes.json()
    
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

  const token = localStorage.getItem('access_token')
  try {
    const res = await fetch(`${import.meta.env.VITE_API_URL}/trips/${tripId}/participants/${participantId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    })

    if (!res.ok) throw new Error('Не вдалося видалити учасника')
    await fetchTripData()
  } catch (error) {
    toast.error(error.message)
  }
}

// Приєднання до поїздки
const joinTrip = async () => {
  const token = localStorage.getItem('access_token')
  try {
    const res = await fetch(`${import.meta.env.VITE_API_URL}/trips/${tripId}/join`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Помилка приєднання')
    }
    await fetchTripData()
  } catch (error) {
    toast.error(error.message)
  }
}

// Вихід з поїздки (ДЛЯ УЧАСНИКА)
const leaveTrip = async () => {
  if (!confirm('Ти дійсно хочеш вийти з цієї поїздки? Всі твої спаковані речі стануть вільними.')) return

  const token = localStorage.getItem('access_token')
  try {
    const res = await fetch(`${import.meta.env.VITE_API_URL}/trips/${tripId}/leave`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Не вдалося вийти з поїздки')
    }
    
    // Після успішного виходу кидаємо користувача на головну сторінку
    router.push('/')
  } catch (error) {
    toast.error(error.message)
  }
}


const createCategory = async (categoryName) => { 
  const token = localStorage.getItem('access_token')
  try {
    const response = await fetch(`${import.meta.env.VITE_API_URL}/trips/${tripId}/categories/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ name: categoryName })
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || 'Не вдалося створити категорію')
    }
    
    await fetchTripData() 
    toast.success("Категорію успішно створено.")
  } catch (error) {
    toast.error(error.message)
  }
}


const addItem = async (payload) => { 
  const token = localStorage.getItem('access_token')
  try {
    const res = await fetch(`${import.meta.env.VITE_API_URL}/items/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        name: payload.name,                  
        trip_id: Number(tripId),
        category_id: Number(payload.categoryId) 
      })
    })

    if (!res.ok) throw new Error('Не вдалося додати річ')

    await fetchTripData()
    toast.success("Річ додано до списку.")
  } catch (error) {
    toast.error(error.message)
  }
}

// Бронювання речі через чекбокс
const toggleItemAssignment = async (item) => {
  const token = localStorage.getItem('access_token')
  const isAssigned = !!item.assigned_user
  
  try {
    const res = await fetch(`${import.meta.env.VITE_API_URL}/items/${item.id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      // Відправляємо тільки статус галочки (true або false)
      body: JSON.stringify({
        is_packed: !isAssigned 
      })
    })

    if (!res.ok) {
      const errData = await res.json()
      throw new Error(errData.detail || 'Не вдалося оновити статус речі')
    }
    await fetchTripData()
  } catch (error) {
    toast.error(error.message)
    console.error(error)
  }
}

// Видалення речі (ТІЛЬКИ ДЛЯ ОРГАНІЗАТОРА)
const deleteItem = async (itemId) => {
  if (!confirm('Видалити цю річ зі списку?')) return

  const token = localStorage.getItem('access_token')
  try {
    const res = await fetch(`${import.meta.env.VITE_API_URL}/items/${itemId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    })

    if (!res.ok) throw new Error('Не вдалося видалити річ')
    await fetchTripData()
  } catch (error) {
    toast.error(error.message)
  }
}

// Видалення поїздки (ТІЛЬКИ ДЛЯ ОРГАНІЗАТОРА)
const deleteTrip = async () => {
  if (!confirm('УВАГА! Ти дійсно хочеш видалити цю поїздку назавжди?')) return

  const token = localStorage.getItem('access_token')
  try {
    const res = await fetch(`${import.meta.env.VITE_API_URL}/trips/${tripId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    })

    if (!res.ok) throw new Error('Не вдалося видалити поїздку')
    
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
        :currentUser="currentUser"
        :ownerUsername="trip.owner?.username"
        @toggle="toggleItemAssignment"
        @delete="deleteItem"
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