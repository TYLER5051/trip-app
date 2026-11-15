<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import api from '../services/api'
import UserAvatar from './UserAvatar.vue'

const props = defineProps({
  // Без tripId — стрічка профілю (/users/me/activities), з tripId — стрічка поїздки.
  tripId: { type: Number, required: false, default: null },
  // Батько збільшує це число після кожної мутації — стрічка оновлюється без F5.
  refreshKey: { type: Number, required: false, default: 0 }
})

const PAGE_SIZE = 8

const items = ref([])
const total = ref(0)
const isLoading = ref(true)
const isLoadingMore = ref(false)
const errorMessage = ref('')
const offset = ref(0)

let seq = 0

const hasMore = computed(() => items.value.length < total.value)
const showTripTitle = computed(() => !props.tripId)

const rtf = new Intl.RelativeTimeFormat('uk', { numeric: 'auto' })

const UNITS = [
  ['year', 31536000],
  ['month', 2592000],
  ['week', 604800],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
  ['second', 1]
]

function timeAgo(iso) {
  const then = new Date(iso).getTime()
  const seconds = Math.round((then - Date.now()) / 1000)
  if (!Number.isFinite(seconds)) return ''
  const abs = Math.abs(seconds)
  for (const [unit, size] of UNITS) {
    if (abs >= size) {
      return rtf.format(Math.round(seconds / size), unit)
    }
  }
  return rtf.format(seconds, 'second')
}

// Форми дієслів нейтральні/чоловічі, без роду — хто саме діяв видно з імені вище.
function actionText(act) {
  const d = act.details || {}
  const quote = (s) => (s ? `«${s}»` : '')
  switch (act.action) {
    case 'item_created':
      return `додав річ ${quote(d.name)}`
    case 'item_assigned':
      return d.quantity > 1
        ? `взяв річ ${quote(d.name)} ×${d.quantity}`
        : `взяв річ ${quote(d.name)}`
    case 'item_unassigned':
      return `зняв позначку з ${quote(d.name)}`
    case 'item_moved':
      return `переніс ${quote(d.name)} у ${quote(d.to || 'Інше')}`
    case 'item_deleted':
      return `видалив річ ${quote(d.name)}`
    case 'category_deleted':
      return `видалив категорію ${quote(d.name)}`
    case 'trip_created':
      return `створив поїздку ${quote(d.title)}`
    case 'participant_joined':
      return 'приєднався до поїздки'
    default:
      return act.action
  }
}

const endpoint = () =>
  props.tripId ? `/trips/${props.tripId}/activities` : '/users/me/activities'

const fetchFeed = async (reset = true) => {
  const current = ++seq
  if (reset) {
    offset.value = 0
    if (items.value.length === 0) isLoading.value = true
  } else {
    isLoadingMore.value = true
  }
  errorMessage.value = ''

  try {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(reset ? 0 : offset.value)
    })
    const data = await api.get(`${endpoint()}?${params.toString()}`)
    if (current !== seq) return
    items.value = reset ? data.items : [...items.value, ...data.items]
    total.value = data.total
  } catch (error) {
    if (current !== seq) return
    errorMessage.value = error.message
  } finally {
    if (current === seq) {
      isLoading.value = false
      isLoadingMore.value = false
    }
  }
}

const loadMore = () => {
  offset.value += PAGE_SIZE
  fetchFeed(false)
}

onMounted(() => fetchFeed())

watch(() => props.refreshKey, () => fetchFeed())
</script>

<template>
  <div class="activity-feed">
    <div v-if="isLoading && items.length === 0" class="feed-status">Завантаження дій...</div>
    <div v-else-if="errorMessage" class="feed-status feed-error">{{ errorMessage }}</div>

    <template v-else>
      <ul v-if="items.length" class="feed-list">
        <li v-for="act in items" :key="act.id" class="feed-item">
          <UserAvatar
            :username="act.actor?.username"
            :color="act.actor?.avatar_color"
            :size="28"
          />
          <div class="feed-text">
            <span class="feed-actor">{{ act.actor?.username || 'Видалений користувач' }}</span>
            {{ actionText(act) }}
            <router-link
              v-if="showTripTitle"
              :to="`/trips/${act.trip_id}`"
              class="feed-trip"
              :title="act.trip?.title"
            >
              · {{ act.trip?.title }}
            </router-link>
          </div>
          <span class="feed-time">{{ timeAgo(act.created_at) }}</span>
        </li>
      </ul>
      <div v-else class="feed-status">Поки що немає заходів у стрічці.</div>

      <button v-if="hasMore" class="feed-more" :disabled="isLoadingMore" @click="loadMore">
        {{ isLoadingMore ? 'Завантаження...' : `Показати ще (${total - items.length})` }}
      </button>
    </template>
  </div>
</template>

<style scoped>
.activity-feed {
  font-size: 13px;
}
.feed-status {
  color: #7f8c8d;
  padding: 8px 0;
  text-align: center;
}
.feed-error {
  color: #e74c3c;
}
.feed-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.feed-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid #f2f4f6;
}
.feed-item:last-child {
  border-bottom: none;
}
.feed-text {
  flex: 1;
  min-width: 0;
  color: #34495e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.feed-actor {
  font-weight: bold;
  color: #2c3e50;
}
.feed-trip {
  color: #42b883;
  font-size: 12px;
  font-weight: bold;
  text-decoration: none;
}
.feed-trip:hover {
  text-decoration: underline;
}
.feed-time {
  color: #95a5a6;
  font-size: 11px;
  white-space: nowrap;
  margin-left: 8px;
  flex-shrink: 0;
}
.feed-more {
  display: block;
  margin: 12px auto 0;
  background-color: #42b883;
  color: white;
  border: none;
  padding: 7px 18px;
  border-radius: 16px;
  font-weight: bold;
  font-size: 12px;
  cursor: pointer;
}
.feed-more:hover:not(:disabled) {
  background-color: #35495e;
}
.feed-more:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>