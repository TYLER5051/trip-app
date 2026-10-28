<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import api from '../services/api'

const route = useRoute()
const router = useRouter()

const token = route.params.token
const errorMessage = ref('')

onMounted(async () => {
  try {
    const data = await api.post(`/trips/invite/${token}`)
    toast.success(`Ви приєдналися до поїздки «${data.title}»!`)
    router.replace(`/trips/${data.trip_id}`)
  } catch (error) {
    errorMessage.value = error.message
  }
})
</script>

<template>
  <div class="invite-container">
    <div v-if="!errorMessage" class="invite-loading">
      Приєднуємось до поїздки...
    </div>
    <div v-else class="invite-error">
      <h2>Не вдалося приєднатися</h2>
      <p>{{ errorMessage }}</p>
      <button @click="router.push('/')" class="back-btn">На головну</button>
    </div>
  </div>
</template>

<style scoped>
.invite-container {
  max-width: 500px;
  margin: 60px auto;
  text-align: center;
  background: white;
  padding: 30px;
  border-radius: 10px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}
.invite-loading {
  color: #666;
  font-size: 16px;
}
.invite-error h2 {
  color: #e74c3c;
  margin-top: 0;
}
.invite-error p {
  color: #7f8c8d;
}
.back-btn {
  background-color: #42b883;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 5px;
  font-weight: bold;
  cursor: pointer;
}
.back-btn:hover {
  background-color: #35495e;
}
</style>