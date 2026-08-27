<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const username = ref('')
const password = ref('')
const errorMessage = ref('')
const isLoading = ref(false)
const isRegister = ref(false)

const submitForm = async () => {
  isLoading.value = true
  errorMessage.value = ''

  try {
    if (isRegister.value) {
      // реєстрація
      const response = await fetch('http://localhost:8000/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json', 
        },
        body: JSON.stringify({
          username: username.value,
          password: password.value
        }),
      })

      if (!response.ok) {
        if (response.status === 400) {
          throw new Error('Користувач з таким логіном вже існує!')
        }
        throw new Error('Помилка при реєстрації')
      }

      alert('Реєстрація успішна! Тепер увійдіть зі своїми даними.')
      isRegister.value = false 
      password.value = ''      

    } else {
      // логін
      const formData = new URLSearchParams()
      formData.append('username', username.value)
      formData.append('password', password.value)

      const response = await fetch('http://localhost:8000/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData,
      })

      if (!response.ok) {
        throw new Error('Неправильний логін або пароль')
      }

      const data = await response.json()
      
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('username', username.value)

      router.push('/')
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
            placeholder="Введи пароль"
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