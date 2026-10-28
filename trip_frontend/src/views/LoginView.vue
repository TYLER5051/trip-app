<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import api from '../services/api'

const route = useRoute()
const router = useRouter()

const redirectTo = route.query.redirect ? String(route.query.redirect) : '/'

const previewTrip = ref(null)

const loadTripPreview = async () => {
  const match = redirectTo.match(/^\/invite\/([A-Za-z0-9_-]+)/)
  if (!match) return

  try {
    previewTrip.value = await api.get(`/trips/invite/${match[1]}/preview`)
  } catch (error) {
    previewTrip.value = null
  }
}

onMounted(loadTripPreview)

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const errorMessage = ref('')
const isLoading = ref(false)
const isRegister = ref(false)

// Валідація перед відправкою
const validate = () => {
  if (!username.value.trim()) {
    errorMessage.value = 'Введіть логін'
    return false
  }

  if (password.value.length < 8) {
    errorMessage.value = 'Пароль має містити щонайменше 8 символів'
    return false
  }

  if (isRegister.value && password.value !== confirmPassword.value) {
    errorMessage.value = 'Паролі не співпадають'
    return false
  }

  return true
}

const submitForm = async () => {
  errorMessage.value = ''
  if (!validate()) return

  isLoading.value = true

  try {
    if (isRegister.value) {
      // реєстрація
      await api.post('/register', { username: username.value.trim(), password: password.value })

      toast.success('Реєстрація успішна! Тепер увійдіть зі своїми даними.')
      isRegister.value = false
      password.value = ''
      confirmPassword.value = ''

    } else {
      // логін
      const data = await api.login(username.value.trim(), password.value)

      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('username', username.value.trim())

      router.push(redirectTo)
    }
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <div v-if="previewTrip" class="trip-preview-card">
      <div class="preview-icon">🌍</div>
      <h3>Це поїздка «{{ previewTrip.title }}»</h3>
      <p v-if="previewTrip.owner">Організатор: <strong>{{ previewTrip.owner.username }}</strong></p>
      <p>Учасників: {{ previewTrip.participants_count }} · Речей: {{ previewTrip.items_count }}</p>
      <p class="preview-hint">Увійди або зареєструйся, щоб приєднатися!</p>
    </div>

    <div class="login-card">
      <h2>{{ isRegister ? 'Реєстрація' : 'Вхід у систему' }}</h2>
      
      <form @submit.prevent="submitForm">
        <div class="form-group">
          <label>Логін</label>
          <input 
            type="text" 
            v-model="username" 
            required 
            placeholder="Введи свій логін"
          />
        </div>

        <div class="form-group">
          <label>Пароль</label>
          <input 
            type="password" 
            v-model="password" 
            required 
            minlength="8"
            placeholder="Мінімум 8 символів"
          />
        </div>

        <div v-if="isRegister" class="form-group">
          <label>Підтверди пароль</label>
          <input 
            type="password" 
            v-model="confirmPassword" 
            required 
            minlength="8"
            placeholder="Повтори пароль"
          />
        </div>

        <div v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </div>

        <button type="submit" :disabled="isLoading" class="submit-btn">
          <span v-if="isLoading">{{ isRegister ? 'Реєстрація...' : 'Входимо...' }}</span>
          <span v-else>{{ isRegister ? 'Зареєструватися' : 'Увійти' }}</span>
        </button>
        
        <div style="text-align: center; margin-top: 15px; font-size: 14px;">
          <span v-if="!isRegister">
            Ще немає акаунту? 
            <a href="#" @click.prevent="isRegister = true" style="color: #42b983; font-weight: bold; text-decoration: none;">Зареєструватися</a>
          </span>
          <span v-else>
            Вже є акаунт? 
            <a href="#" @click.prevent="isRegister = false" style="color: #42b983; font-weight: bold; text-decoration: none;">Увійти</a>
          </span>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 50px;
}
.login-card {
  background: white;
  padding: 30px;
  border-radius: 10px;
  box-shadow: 0 4px 10px rgba(0,0,0,0.1);
  width: 100%;
  max-width: 400px;
}
.trip-preview-card {
  background: white;
  padding: 25px 30px;
  border-radius: 10px;
  box-shadow: 0 4px 10px rgba(0,0,0,0.1);
  width: 100%;
  max-width: 400px;
  margin-bottom: 20px;
  text-align: center;
  border-top: 4px solid #42b883;
}
.trip-preview-card h3 {
  color: #2c3e50;
  margin: 10px 0;
}
.trip-preview-card p {
  color: #7f8c8d;
  margin: 6px 0;
}
.preview-icon {
  font-size: 40px;
}
.preview-hint {
  color: #2980b9 !important;
  font-weight: bold;
  margin-top: 10px !important;
}
h2 {
  text-align: center;
  color: #2c3e50;
  margin-bottom: 25px;
}
.form-group {
  margin-bottom: 20px;
}
.form-group label {
  display: block;
  margin-bottom: 8px;
  color: #34495e;
  font-weight: bold;
}
.form-group input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 5px;
  font-size: 16px;
  box-sizing: border-box;
}
.error-message {
  color: #e74c3c;
  margin-bottom: 15px;
  text-align: center;
  font-size: 14px;
}
.submit-btn {
  width: 100%;
  padding: 12px;
  background-color: #42b883;
  color: white;
  border: none;
  border-radius: 5px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
  transition: background 0.2s;
}
.submit-btn:hover {
  background-color: #35495e;
}
.submit-btn:disabled {
  background-color: #95a5a6;
  cursor: not-allowed;
}
</style>