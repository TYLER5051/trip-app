const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Коли бекенд відповідає 401 — токен протух або невалідний.
// Чистимо localStorage і повертаємо користувача на сторінку логіну.
function handleUnauthorized() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('username')
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login'
  }
}

// Універсальна обгортка над fetch. Всі запити застосунку йдуть через неї:
//  - сама підставляє Authorization: Bearer <token>;
//  - сама ставить Content-Type: application/json (окрім form-запитів);
//  - на 401 автоматично розлогінює і перекидає на /login (окрім "public" ендпоінтів,
//    де 401 означає просто невірні дані, напр. на /login);
//  - помилки бекенду перетворює в зручний Error з текстом з detail.
async function request(endpoint, { method = 'GET', body, headers = {}, form = false, public: isPublic = false } = {}) {
  const token = localStorage.getItem('access_token')

  const finalHeaders = { ...headers }
  if (!form) finalHeaders['Content-Type'] = 'application/json'
  if (token) finalHeaders['Authorization'] = `Bearer ${token}`

  const options = { method, headers: finalHeaders }
  if (body !== undefined) {
    options.body = form ? body : JSON.stringify(body)
  }

  const res = await fetch(`${API_URL}${endpoint}`, options)

  if (res.status === 401) {
    const data = await res.json().catch(() => null)

    if (isPublic) {
      // Публічний ендпоінт (логін) — 401 означає «невірний логін або пароль»,
      // а не протухлу сесію. Чистимо старий токен, але НЕ редиректимо.
      localStorage.removeItem('access_token')
      localStorage.removeItem('username')
      throw new Error(data?.detail || 'Невірний логін або пароль')
    }

    handleUnauthorized()
    throw new Error('Сесія закінчилась. Будь ласка, увійдіть знову.')
  }

  if (res.status === 204) return null

  const data = await res.json().catch(() => null)

  if (!res.ok) {
    const detail = data && data.detail
      ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
      : 'Щось пішло не так'
    const error = new Error(detail)
    error.status = res.status
    throw error
  }

  return data
}

export default {
  get: (endpoint) => request(endpoint),
  post: (endpoint, body) => request(endpoint, { method: 'POST', body }),
  patch: (endpoint, body) => request(endpoint, { method: 'PATCH', body }),
  delete: (endpoint) => request(endpoint, { method: 'DELETE' }),
  // /login приймає дані у форматі x-www-form-urlencoded (OAuth2), тому form: true.
  // public: true — щоб 401 тут означав «невірний пароль», а не «вийди з сесії».
  login: (username, password) => request('/login', {
    method: 'POST',
    form: true,
    public: true,
    body: new URLSearchParams({ username, password })
  })
}
