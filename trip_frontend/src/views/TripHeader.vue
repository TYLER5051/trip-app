<script setup>
import { toast } from 'vue3-toastify'

const props = defineProps({
  trip: { type: Object, required: true },
  currentUser: { type: String, required: true },
  isParticipant: { type: Boolean, required: true }
})

const emit = defineEmits(['join', 'leave', 'delete'])

const copyTripLink = async () => {
  try {
    // localhost HTTPS
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(window.location.href)
      toast.success('Посилання скопійовано! Відправте його друзям.')
      return
    }

    // HTTP
    const textArea = document.createElement("textarea")
    textArea.value = window.location.href
    
    textArea.style.position = "absolute"
    textArea.style.opacity = "0"
    
    document.body.appendChild(textArea)
    textArea.select()
    
    const successful = document.execCommand('copy')
    textArea.remove()

    if (successful) {
      toast.success('Посилання скопійовано! Відправте його друзям.')
    } else {
      throw new Error('Копіювання заблоковано браузером')
    }
  } catch (error) {
    toast.error('Браузер заблокував копіювання. Просто скопіюйте посилання з адресного рядка.')
  }
}
</script>

<template>
  <div class="trip-header">
    <h1>{{ trip.title }}</h1>
    <p class="owner">Організатор: <strong>{{ trip.owner?.username }}</strong></p>
    
    <div class="actions-bar">
      <!-- Якщо ми НЕ організатор і ЩЕ НЕ учасник -->
      <button 
        v-if="trip.owner?.username !== currentUser && !isParticipant" 
        @click="emit('join')" 
        class="join-btn"
      >
        Приєднатися до поїздки
      </button>
      
      <!-- Якщо ми ВЖЕ приєдналися -->
      <div v-if="trip.owner?.username !== currentUser && isParticipant" class="joined-status">
        <span class="joined-badge">Ти є учасником</span>
        <button @click="emit('leave')" class="leave-btn">Вийти з поїздки</button>
      </div>
      
      <!-- Кнопка видалення поїздки для організатора -->
      <button 
        v-if="trip.owner?.username === currentUser" 
        @click="emit('delete')" 
        class="delete-trip-btn"
      >
        Видалити поїздку
      </button>

      <button @click="copyTripLink" class="copy-link-btn">
        Скопіювати посилання на поїздку
      </button>
    </div>
  </div>
</template>

<style scoped>
.trip-header {
  background: white;
  padding: 20px;
  border-radius: 10px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  margin-bottom: 20px;
}
.trip-header h1 {
  margin: 0 0 10px 0;
  color: #2c3e50;
}
.owner {
  color: #7f8c8d;
  margin-bottom: 15px;
}
.actions-bar { 
  display: flex; 
  gap: 10px; 
}
.join-btn {
  background-color: #3498db;
  color: white;
  border: none;
  padding: 8px 15px;
  border-radius: 5px;
  cursor: pointer;
  font-weight: bold;
}
.joined-status {
  display: flex;
  align-items: center;
  gap: 15px;
}
.joined-badge { 
  background-color: #27ae60; 
  color: white; 
  padding: 8px 15px; 
  border-radius: 5px; 
  font-weight: bold; 
}
.leave-btn {
  background-color: #f39c12; 
  color: white;
  border: none;
  padding: 8px 15px;
  border-radius: 5px;
  cursor: pointer;
  font-weight: bold;
}
.leave-btn:hover {
  background-color: #d68910;
}
.delete-trip-btn { 
  background-color: #e74c3c; 
  color: white; 
  border: none; 
  padding: 8px 15px; 
  border-radius: 5px; 
  cursor: pointer; 
  font-weight: bold; 
}
.delete-trip-btn:hover { 
  background-color: #c0392b; 
}
.copy-link-btn {
  background-color: #4CAF50; 
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  margin-left: 10px;
  transition: background-color 0.3s;
}
.copy-link-btn:hover {
  background-color: #45a049;
}
</style>