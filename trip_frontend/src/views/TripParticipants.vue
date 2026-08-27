<script setup>

const props = defineProps({
  participants: { type: Array, required: true },
  ownerUsername: { type: String, required: false },
  currentUser: { type: String, required: true }
})


const emit = defineEmits(['remove'])
</script>

<template>
  <div class="participants-card" v-if="participants && participants.length > 0">
    <h3>👥 Учасники ({{ participants.length }})</h3>
    <ul class="participants-list">
      <li v-for="participant in participants" :key="participant.id">
        <span>👤 {{ participant.username }}</span>
        
        <!-- Кнопка видалення учасника (Тільки для організатора) -->
        <button 
          v-if="ownerUsername === currentUser"
          @click="emit('remove', participant.id)"
          class="remove-participant-btn"
          title="Видалити учасника"
        >
          ❌
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.participants-card { 
  background: white; 
  padding: 20px; 
  border-radius: 10px; 
  box-shadow: 0 2px 5px rgba(0,0,0,0.05); 
  margin-bottom: 20px; 
}
.participants-card h3 { 
  margin-top: 0; 
  color: #2c3e50; 
  font-size: 16px; 
  margin-bottom: 10px; 
}
.participants-list { 
  list-style: none; 
  padding: 0; 
  margin: 0; 
  display: flex; 
  flex-wrap: wrap; 
  gap: 10px; 
}
.participants-list li { 
  background-color: #f1f2f6; 
  padding: 5px 12px; 
  border-radius: 15px; 
  font-size: 14px; 
  font-weight: 500; 
  display: flex; 
  align-items: center; 
  gap: 8px; 
}
.remove-participant-btn { 
  background: none; 
  border: none; 
  cursor: pointer; 
  font-size: 12px; 
  opacity: 0.6; 
  padding: 0; 
}
.remove-participant-btn:hover { 
  opacity: 1; 
  color: #e74c3c; 
}
</style>