<script setup>
import { watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import auth from './stores/auth'

const router = useRouter()
const route = useRoute()

// Хедер читає реактивний стан з auth store. Слідкуємо за зміною URL і
// синхронізуємо його з localStorage (на випадок змін поза стори).
watch(() => route.path, () => {
  auth.syncFromStorage()
})

const handleLogout = () => {
  auth.clearSession()
  router.push('/login')
}
</script>

<template>
  <div id="app">
    <nav class="navbar">
      <div class="nav-left">
        <router-link v-if="auth.isLoggedIn" to="/" class="nav-link">
          Поїздки
        </router-link>
      </div>
      
      <div class="nav-right">
        <router-link v-if="!auth.isLoggedIn" to="/login" class="nav-link">Увійти</router-link>
        
        <template v-else>
          <router-link to="/profile" class="nav-link user-link">👤 {{ auth.username }}</router-link>
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
.user-link {
  color: #bdc3c7;
  font-size: 14px;
}
.user-link.router-link-active {
  color: #42b883;
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