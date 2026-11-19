<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import api from '../services/api'
import TripHeader from './TripHeader.vue'
import TripParticipants from './TripParticipants.vue'
import TripItemForm from './TripItemForm.vue'
import TripItemList from './TripItemList.vue'
import TripCopyItems from './TripCopyItems.vue'
import ActivityFeed from '../components/ActivityFeed.vue'

const route = useRoute()
const router = useRouter()
const tripId = computed(() => route.params.id)
const historyVersion = ref(0)
const activeTab = ref('items')

const trip = ref(null)
const isArchived = computed(() => !!trip.value?.is_archived)
const categories = ref([])
const isLoading = ref(true)
const errorMessage = ref('')
const accessError = ref(false)

// Лічильник завантажень поїздки: старі відповіді (після швидкого перемикання
// між поїздками) ігноруємо
const tripSeq = ref(0)

// Поточного користувача беремо з /users/me як числовий id — усі перевірки прав
// робимо за id (не за username), щоб зміна логіна не ламала кнопки.
const currentUserId = ref(null)
const pendingItemId = ref(null)
const isAddingItem = ref(false)
const isCreatingCategory = ref(false)
const isCopyingTrip = ref(false)

// ---- Речі беремо з сервера: пошук (GET /trips/:id/items/), без пагінації ----
const items = ref([])
const itemSearchInput = ref('')
const itemQ = ref('')

let itemSearchTimer = null
let itemsSeq = 0

watch(itemSearchInput, () => {
  clearTimeout(itemSearchTimer)
  itemSearchTimer = setTimeout(() => {
    itemQ.value = itemSearchInput.value.trim()
    fetchItems()
  }, 300)
})

onUnmounted(() => {
  clearTimeout(itemSearchTimer)
})

// race-guard: якщо користувач швидко ввів новий пошук або змінив дані,
// відповідь старого запиту ігнорується.
// Бекенд віддає максимум 100 речей за запит. Куди більше 1 сторінки — решту
// качаємо паралельно (Promise.all), щоб не тягнути сторінки послідовно.
const fetchItems = async () => {
  const seq = ++itemsSeq
  const params = new URLSearchParams()
  params.set('limit', '100')
  if (itemQ.value) params.set('q', itemQ.value)

  const pageUrl = (offset) => {
    const p = new URLSearchParams(params)
    p.set('offset', String(offset))
    return `/trips/${tripId.value}/items/?${p.toString()}`
  }

  try {
    const first = await api.get(pageUrl(0))
    if (seq !== itemsSeq) return

    const total = first.total ?? first.items.length
    const pagesNeeded = Math.max(1, Math.ceil(total / 100))

    if (pagesNeeded <= 1) {
      items.value = first.items
      return
    }

    const rest = await Promise.all(
      Array.from({ length: pagesNeeded - 1 }, (_, i) => api.get(pageUrl((i + 1) * 100)))
    )
    if (seq !== itemsSeq) return

    items.value = [].concat(first.items, ...rest.map(r => r.items))
  } catch (error) {
    if (seq !== itemsSeq) return
    if (error.status === 403 || error.status === 404) {
      accessError.value = true
    } else if (items.value.length > 0) {
      toast.error(error.message)
    }
  }
}

// Завантаження даних поїздки, категорій та речей
const fetchTripData = async () => {
  const seq = tripSeq.value
  try {
    const [tripData, catsData] = await Promise.all([
      api.get(`/trips/${tripId.value}`),
      api.get(`/trips/${tripId.value}/categories/`)
    ])
    if (seq !== tripSeq.value) return
    trip.value = tripData
    categories.value = catsData
    await fetchItems()
    if (seq !== tripSeq.value) return
    historyVersion.value += 1
  } catch (error) {
    if (seq !== tripSeq.value) return
    if (error.status === 403 || error.status === 404) {
      accessError.value = true
    } else {
      errorMessage.value = error.message
    }
  } finally {
    if (seq === tripSeq.value) isLoading.value = false
  }
}

//оновлюємо одну річ у локальному списку за id — без перезавантаження всього списку
const applyItemUpdate = (updated) => {
  if (!updated) return
  const idx = items.value.findIndex(i => i.id === updated.id)
  if (idx !== -1) items.value[idx] = updated
  else items.value.push(updated)
}

// Оновлюємо лише статистику поїздки (список речей уже актуальний)
const refreshTripStats = async () => {
  try {
    trip.value = await api.get(`/trips/${tripId.value}`)
  } catch {
    // статистика не критична — лишаємо попередню
  }
  historyVersion.value += 1
}

// Повне синхронізування після помилки: список має збігатися з сервером
const reloadItemsAndStats = async () => {
  try {
    const [freshTrip] = await Promise.all([
      api.get(`/trips/${tripId.value}`),
      fetchItems()
    ])
    trip.value = freshTrip
  } catch (error) {
    if (error.status !== 403 && error.status !== 404) toast.error(error.message)
  }
  historyVersion.value += 1
}

// Групування речей за категоріями
const groupedItems = computed(() => {
  const groups = {}
  // Спочатку кладемо всі категорії, щоб навіть порожні були видимі
  // (інакше порожню категорію неможливо було б видалити з інтерфейсу)
  categories.value.forEach(cat => {
    groups[cat.name] = []
  })

  items.value.forEach(item => {
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
  return trip.value.participants.some(p => p.id === currentUserId.value)
})

const packingPercent = computed(() => {
  const total = trip.value?.total_items || 0
  if (!total) return 0
  return Math.round(((trip.value?.packed_items || 0) / total) * 100)
})

// ---- Наслідування речей з минулої поїздки ----
const showCopyModal = ref(false)
const copySourceTrips = ref([])
const isCopyModalLoading = ref(false)

const openCopyModal = async () => {
  showCopyModal.value = true
  copySourceTrips.value = []
  isCopyModalLoading.value = true
  try {
    const [active, archived] = await Promise.all([
      api.get('/trips/?limit=100'),
      api.get('/trips/?role=archived&limit=100')
    ])
    const byId = new Map()
    ;[...active.items, ...archived.items].forEach(t => {
      if (t.id != tripId.value && t.total_items > 0) byId.set(t.id, t)
    })
    copySourceTrips.value = [...byId.values()]
  } catch (error) {
    toast.error(error.message)
  } finally {
    isCopyModalLoading.value = false
  }
}

const handleCopyItems = async (sourceTripId) => {
  isCopyingTrip.value = true
  try {
    const res = await api.post(`/trips/${tripId.value}/copy-items`, { source_trip_id: sourceTripId })
    showCopyModal.value = false
    await fetchTripData()
    const extra = res.skipped_items
      ? ` Пропущено дублікатів: ${res.skipped_items}.`
      : ''
    toast.success(`${res.message} Додано речей: ${res.copied_items}.${extra}`)
  } catch (error) {
    toast.error(error.message)
  } finally {
    isCopyingTrip.value = false
  }
}

// Видалення учасника (ТІЛЬКИ ДЛЯ ОРГАНІЗАТОРА)
const removeParticipant = async (participantId) => {
  const participant = trip.value?.participants?.find(p => p.id === participantId)
  const freedCount = items.value.reduce((sum, item) => {
    const taken = (item.assignments || []).filter(a => a.user.id === participantId)
    return sum + taken.reduce((s, a) => s + (a.quantity || 0), 0)
  }, 0)

  const who = participant ? `«${participant.username}»` : `ID ${participantId}`
  if (!confirm(`Видалити учасника ${who}? Його взяті речі (${freedCount}) стануть вільними.`)) return

  try {
    await api.delete(`/trips/${tripId.value}/participants/${participantId}`)
    await fetchTripData()
    toast.success(freedCount > 0 ? `Речі учасника звільнено: ${freedCount} шт.` : 'Учасника видалено.')
  } catch (error) {
    toast.error(error.message)
  }
}

// Передача прав організатора іншому учаснику (ТІЛЬКИ ДЛЯ ОРГАНІЗАТОРА)
const transferOwnership = async (participantId) => {
  const participant = trip.value?.participants?.find(p => p.id === participantId)
  const who = participant ? `«${participant.username}»` : `ID ${participantId}`
  if (!confirm(`Передати права організатора учаснику ${who}? Ви станете звичайним учасником.`)) return

  try {
    await api.patch(`/trips/${tripId.value}/transfer-owner`, { new_owner_id: participantId })
    await fetchTripData()
    toast.success(`Права організатора передано ${who}`)
  } catch (error) {
    toast.error(error.message)
  }
}

// Вихід з поїздки (ДЛЯ УЧАСНИКА)
const leaveTrip = async () => {
  if (!confirm('Ти дійсно хочеш вийти з цієї поїздки? Всі твої спаковані речі стануть вільними.')) return

  try {
    await api.delete(`/trips/${tripId.value}/leave`)

    // Після успішного виходу кидаємо користувача на головну сторінку
    router.push('/')
  } catch (error) {
    toast.error(error.message)
  }
}


const createCategory = async (categoryName) => {
  isCreatingCategory.value = true
  try {
    await api.post(`/trips/${tripId.value}/categories/`, { name: categoryName })

    await fetchTripData()
    toast.success("Категорію успішно створено.")
  } catch (error) {
    toast.error(error.message)
  } finally {
    isCreatingCategory.value = false
  }
}


// Перейменування категорії (тільки організатор або автор категорії)
const renameCategory = async ({ id, name }) => {
  if (!name || name.trim().length < 2) {
    toast.error('Назва категорії має містити щонайменше 2 символи')
    return
  }

  try {
    await api.patch(`/trips/${tripId.value}/categories/${id}`, { name: name.trim() })

    await fetchTripData()
    toast.success('Категорію перейменовано.')
  } catch (error) {
    toast.error(error.message)
  }
}

// Видалення категорії (тільки організатор або автор) — речі переносяться в «Інше»
// або у вибрану категорію через move_to
const categoryToDelete = ref(null)
const deleteTargetCategoryId = ref('')
const isDeletingCategory = ref(false)

const toDeleteItemCount = computed(() => {
  const cat = categoryToDelete.value
  if (!cat) return 0
  return items.value.filter(i => i.category_id === cat.id).length
})

const otherCategories = computed(() =>
  (categories.value || []).filter(c => categoryToDelete.value && c.id !== categoryToDelete.value.id)
)

const askDeleteCategory = (category) => {
  deleteTargetCategoryId.value = ''
  categoryToDelete.value = category
}

const closeDeleteCategory = () => {
  if (isDeletingCategory.value) return
  categoryToDelete.value = null
}

const confirmDeleteCategory = async () => {
  const category = categoryToDelete.value
  if (!category) return

  isDeletingCategory.value = true
  try {
    const moveTo = deleteTargetCategoryId.value || null
    const query = moveTo ? `?move_to=${moveTo}` : ''
    const res = await api.delete(`/trips/${tripId.value}/categories/${category.id}${query}`)
    categoryToDelete.value = null
    await fetchTripData()
    toast.success(res.message || 'Категорію видалено.')
  } catch (error) {
    toast.error(error.message)
  } finally {
    isDeletingCategory.value = false
  }
}

const addItem = async (payload) => {
  isAddingItem.value = true
  try {
    await api.post('/items/', {
      name: payload.name,
      trip_id: Number(tripId.value),
      category_id: Number(payload.categoryId),
      quantity: payload.quantity ?? 1,
      note: payload.note || null,
      is_critical: payload.is_critical ?? false
    })

    await fetchTripData()
    toast.success("Річ додано до списку.")
  } catch (error) {
    toast.error(error.message)
  } finally {
    isAddingItem.value = false
  }
}

// Взяти річ через чекбокс: кожен учасник «бере» свій слот (поки є місця = quantity)
const toggleItemAssignment = async (item) => {
  const assignedByMe = (item.assignments || []).some(a => a.user.id === currentUserId.value)

  pendingItemId.value = item.id
  try {
    const updated = assignedByMe
      ? await api.delete(`/items/${item.id}/assign`)
      : await api.post(`/items/${item.id}/assign`, { quantity: 1 })

    // бекенд повертає повний ItemResponse — оновлюємо лише цю річ у списку,
    // не перезавантажуючи весь чекліст
    applyItemUpdate(updated)
    await refreshTripStats()
  } catch (error) {
    toast.error(error.message)
    // Навіть при помилці синхронізуємо список, щоб чекбокс повернувся
    // до фактичного стану на сервері.
    await reloadItemsAndStats()
  } finally {
    if (pendingItemId.value === item.id) pendingItemId.value = null
  }
}

// Зміна своєї кількості через степер (лише для своєї позначки)
const changeMyQuantity = async ({ itemId, quantity }) => {
  pendingItemId.value = itemId
  try {
    const updated = quantity <= 0
      ? await api.delete(`/items/${itemId}/assign`)
      : await api.post(`/items/${itemId}/assign`, { quantity })
    applyItemUpdate(updated)
    await refreshTripStats()
  } catch (error) {
    toast.error(error.message)
    await reloadItemsAndStats()
  } finally {
    if (pendingItemId.value === itemId) pendingItemId.value = null
  }
}

// Зняти річ, яку взяв інший учасник, — доступно тільки організатору поїздки
const unassignOther = async ({ item, user }) => {
  pendingItemId.value = item.id
  try {
    const updated = await api.delete(`/items/${item.id}/assign?user_id=${user.id}`)
    toast.success(`Позначку ${user.username} знято. Річ знову вільна.`)
    applyItemUpdate(updated)
    await refreshTripStats()
  } catch (error) {
    toast.error(error.message)
    await reloadItemsAndStats()
  } finally {
    if (pendingItemId.value === item.id) pendingItemId.value = null
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

// Перенесення речі в іншу категорію через drag & drop (тільки організатор або автор речі)
const moveItem = async ({ itemId, categoryId }) => {
  try {
    await api.patch(`/items/${itemId}`, { category_id: categoryId })
    await fetchTripData()
    toast.success('Річ переміщено.')
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
    await api.delete(`/trips/${tripId.value}`)
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
    await api.patch(`/trips/${tripId.value}`, { title: newTitle.trim() })

    await fetchTripData()
    toast.success('Поїздку перейменовано.')
  } catch (error) {
    toast.error(error.message)
  }
}

// Архівація / розархівація поїздки (тільки організатор)
const archiveTrip = async () => {
  if (!confirm('Архівувати поїздку? Вона зникне зі списку активних, але всі дані збережуться.')) return

  try {
    const fresh = await api.post(`/trips/${tripId.value}/archive`)
    trip.value = fresh
    toast.success('Поїздку заархівовано.')
  } catch (error) {
    toast.error(error.message)
  }
}

const unarchiveTrip = async () => {
  try {
    const fresh = await api.post(`/trips/${tripId.value}/unarchive`)
    trip.value = fresh
    toast.success('Поїздку повернуто з архіву.')
  } catch (error) {
    toast.error(error.message)
  }
}

// Зміна дат поїздки (тільки організатор)
const changeTripDates = async ({ start_date, end_date }) => {
  try {
    const fresh = await api.patch(`/trips/${tripId.value}`, { start_date, end_date })
    trip.value = fresh
    toast.success('Дати поїздки збережено.')
  } catch (error) {
    toast.error(error.message)
  }
}

const fetchCurrentUser = async () => {
  try {
    const me = await api.get('/users/me')
    currentUserId.value = me?.id ?? null
  } catch {
    // 401 — api сам перекидає на /login
  }
}

const loadTrip = async () => {
  const seq = ++tripSeq.value
  isLoading.value = true
  await fetchCurrentUser()
  if (seq !== tripSeq.value) return
  await fetchTripData()
}

// переміщення між поїздками без розмонтування компонента (меню, посилання) —
// скидаємо старий стан (помилки, пошук, вкладку, вибір) і вантажимо нову поїздку.
// Фільтри списку скидаються перемонтуванням TripItemList через :key="tripId".
watch(() => route.params.id, () => {
  trip.value = null
  categories.value = []
  items.value = []
  itemSearchInput.value = ''
  itemQ.value = ''
  errorMessage.value = ''
  accessError.value = false
  activeTab.value = 'items'
  historyVersion.value = 0
  showCopyModal.value = false
  categoryToDelete.value = null
  loadTrip()
})

onMounted(loadTrip)

</script>

<template>
  <div class="trip-detail-container">
    <div v-if="isLoading" class="loading">Завантаження поїздки...</div>
    <div v-else-if="accessError" class="access-denied-card">
      <div class="access-icon">🔒</div>
      <h2>У вас немає доступу до цієї поїздки</h2>
      <p>Запитайте інвайт-посилання в організатора.</p>
    </div>
    <div v-else-if="errorMessage" class="error">{{ errorMessage }}</div>

    <div v-else-if="trip">
      
      <!-- плашка архіву: режим перегляду -->
      <div v-if="isArchived" class="archive-banner">
        📦 Поїздка в архіві — режим перегляду. Зміни недоступні.
      </div>

      <!-- header -->
      <TripHeader 
        :trip="trip" 
        :currentUserId="currentUserId" 
        :isParticipant="isParticipant"
        :is-archived="isArchived"
        @leave="leaveTrip"
        @delete="deleteTrip"
        @rename="renameTrip"
        @archive="archiveTrip"
        @unarchive="unarchiveTrip"
        @change-dates="changeTripDates"
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
        :owner-id="trip.owner?.id"
        :current-user-id="currentUserId"
        :is-archived="isArchived"
        @remove="removeParticipant"
        @transfer="transferOwnership"
      />
      
      <!-- вкладки: Речі / Історія -->
      <div class="trip-tabs">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'items' }"
          @click="activeTab = 'items'"
        >
          Речі
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'history' }"
          @click="activeTab = 'history'"
        >
          Історія
        </button>
      </div>

      <div v-if="activeTab === 'items'">
        <!-- додавання речей (приховано в архіві) -->
        <TripItemForm
          v-if="!isArchived"
          :categories="categories"
          :is-adding-item="isAddingItem"
          :is-creating-category="isCreatingCategory"
          @add-item="addItem"
          @create-category="createCategory"
        />

        <!-- наслідування речей з минулої поїздки (приховано в архіві) -->
        <div v-if="!isArchived" class="copy-trip-section">
          <button class="copy-trip-btn" @click="openCopyModal">
            ↩ Наслідувати речі з іншої поїздки
          </button>
        </div>

        <!-- список речей -->
        <TripItemList
          :key="tripId"
          :groupedItems="groupedItems"
          :categories="categories"
          :current-user-id="currentUserId"
          :owner-id="trip.owner?.id"
          :is-archived="isArchived"
          :pending-item-id="pendingItemId"
          @toggle="toggleItemAssignment"
          @unassign-other="unassignOther"
          @update-my-quantity="changeMyQuantity"
          @delete="deleteItem"
          @rename="renameItem"
          @update-quantity="updateItemQuantity"
          @move-item="moveItem"
          @unmark-critical="unmarkCritical"
          @rename-category="renameCategory"
          @delete-category="askDeleteCategory"
        />
      </div>

      <div v-else class="history-card">
        <ActivityFeed :trip-id="Number(tripId)" :refresh-key="historyVersion" />
      </div>

      <!-- модалка видалення категорії -->
      <div v-if="categoryToDelete" class="modal-overlay" @click.self="closeDeleteCategory">
        <div class="delete-cat-modal">
          <h3>Видалити категорію «{{ categoryToDelete.name }}»?</h3>
          <p class="hint">
            <template v-if="toDeleteItemCount > 0">
              Речей у категорії: {{ toDeleteItemCount }}. Оберіть, куди їх перенести.
            </template>
            <template v-else>У категорії немає речей.</template>
          </p>
          <label v-if="toDeleteItemCount > 0" class="move-select">
            <span>Перенести речі до:</span>
            <select v-model="deleteTargetCategoryId">
              <option value="">«Інше» (без категорії)</option>
              <option v-for="c in otherCategories" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </label>
          <div class="modal-actions">
            <button class="btn-cancel" :disabled="isDeletingCategory" @click="closeDeleteCategory">
              Скасувати
            </button>
            <button class="btn-danger" :disabled="isDeletingCategory" @click="confirmDeleteCategory">
              {{ isDeletingCategory ? 'Видалення...' : 'Видалити' }}
            </button>
          </div>
        </div>
      </div>

      <!-- модалка наслідування -->
      <TripCopyItems
        v-if="showCopyModal"
        :trips="copySourceTrips"
        :is-loading="isCopyModalLoading"
        :is-copying="isCopyingTrip"
        @close="showCopyModal = false"
        @copy="handleCopyItems"
      />
    </div>
    
  </div>
</template>

<style scoped>
.trip-detail-container {
  max-width: 800px;
  margin: 0 auto;
}
.archive-banner {
  background: #fff8e1;
  border: 1px solid #f1c40f;
  color: #7d6608;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: bold;
  margin-bottom: 20px;
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
.trip-tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}
.tab-btn {
  background: white;
  border: 1px solid #e1e8ed;
  color: #34495e;
  padding: 9px 22px;
  border-radius: 20px;
  font-size: 14px;
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
.copy-trip-section {
  display: flex;
  margin-bottom: 20px;
}
.history-card {
  background: white;
  border-radius: 10px;
  padding: 20px 24px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  margin-top: 20px;
}
.history-card h3 {
  margin: 0 0 8px;
  color: #34495e;
}
.copy-trip-btn {
  background: white;
  color: #3498db;
  border: 1px dashed #3498db;
  padding: 10px 18px;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
}
.copy-trip-btn:hover {
  background: #eaf6ff;
}
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.delete-cat-modal {
  background: white;
  border-radius: 12px;
  padding: 25px;
  width: min(440px, 92vw);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}
.delete-cat-modal h3 {
  margin: 0 0 8px;
  color: #2c3e50;
}
.delete-cat-modal .hint {
  margin: 0 0 14px;
  font-size: 14px;
  color: #7f8c8d;
}
.move-select {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 18px;
  font-size: 13px;
  color: #34495e;
}
.move-select select {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 5px;
  font-size: 14px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.btn-cancel {
  background: #ecf0f1;
  color: #34495e;
  border: none;
  padding: 9px 18px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
.btn-cancel:hover:not(:disabled) {
  background: #dde3e7;
}
.btn-danger {
  background-color: #e74c3c;
  color: white;
  border: none;
  padding: 9px 18px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
.btn-danger:hover:not(:disabled) {
  background-color: #c0392b;
}
.modal-actions button:disabled {
  opacity: 0.6;
  cursor: default;
}
.access-denied-card {
  background: white;
  padding: 40px 30px;
  border-radius: 10px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  text-align: center;
  margin-top: 30px;
}
.access-denied-card h2 {
  color: #2c3e50;
  margin: 10px 0;
}
.access-denied-card p {
  color: #7f8c8d;
}
.access-icon {
  font-size: 48px;
}
</style>