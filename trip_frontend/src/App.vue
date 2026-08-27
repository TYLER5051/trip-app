<script setup>
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

// Створюємо реактивні змінні
const isLoggedIn = ref(!!localStorage.getItem('access_token'))
const username = ref(localStorage.getItem('username') || 'Користувач')

// Слідкуємо за зміною URL. Щойно користувач переходить на іншу сторінку (наприклад, після логіну), 
// ми примусово оновлюємо дані з localStorage.
watch(() => route.path, () => {
  isLoggedIn.value = !!localStorage.getItem('access_token')
  username.value = localStorage.getItem('username') || 'Користувач'
})

const handleLogout = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('username')
  // Оновлюємо стан одразу при натисканні "Вийти"
  isLoggedIn.value = false
  username.value = 'Користувач'
  router.push('/login')
}
</script>

<template>
  <div id="app">
    <nav class="navbar">
      <div class="nav-left">
        <router-link v-if="isLoggedIn" to="/" class="nav-link">
          Поїздки
        </router-link>
      </div>
      
      <div class="nav-right">
        <router-link v-if="!isLoggedIn" to="/login" class="nav-link">Увійти</router-link>
        
        <template v-else>
          <span class="user-badge">👤 {{ username }}</span>
          <button @click="handleLogout" class="logout-btn">Вийти</button>
        </template>
      </div>
    </nav>

    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<style>
body {
  font-family: Arial, sans-serif;
  margin: 0;
  background-color: #f4f6f8;
}
.navbar {
  background-color: #2c3e50;
  padding: 15px 30px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.nav-left, .nav-right {
  display: flex;
  align-items: center;
  gap: 20px;
}
.nav-link {
  color: #ecf0f1;
  text-decoration: none;
  font-weight: bold;
}
.nav-link.router-link-active {
  color: #42b883;
}
.user-badge {
  color: #bdc3c7;
  font-size: 14px;
}
.logout-btn {
  background-color: #e74c3c;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  font-size: 14px;
}
.logout-btn:hover {
  background-color: #c0392b;
}
.content {
  padding: 20px;
}
</style>