import { ref, computed } from 'vue'

// Легковаговий глобальний (синглтонний) реактивний стан автентифікації.
// Ініціалізуємо з localStorage, а будь-які зміни сесії мають йти через
// setSession/clearSession — тоді шапка, аватар і профіль оновлюються миттєво
// без повного перезавантаження сторінки (location.reload()).
const accessToken = ref('')
const username = ref('')

function syncFromStorage() {
  accessToken.value = localStorage.getItem('access_token') || ''
  username.value = localStorage.getItem('username') || ''
}

syncFromStorage()

const isLoggedIn = computed(() => !!accessToken.value)

function setSession(token, name) {
  if (token) localStorage.setItem('access_token', token)
  localStorage.setItem('username', name)
  accessToken.value = token || localStorage.getItem('access_token') || ''
  username.value = name
}

function clearSession() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('username')
  accessToken.value = ''
  username.value = ''
}

export default {
  accessToken,
  username,
  isLoggedIn,
  syncFromStorage,
  setSession,
  clearSession,
}