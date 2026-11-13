import auth from '../stores/auth'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Коли бекенд відповідає 401 — токен протух або невалідний.
// Чистимо сесію (localStorage + реактивний стан) і повертаємо користувача на логін.
function handleUnauthorized() {
  auth.clearSession()
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login'
  }
}

const FIELD_LABELS = {
  title: 'Назва поїздки',
  name: 'Назва',
  username: 'Логін',
  password: 'Пароль',
  old_password: 'Поточний пароль',
  new_password: 'Новий пароль',
  current_password: 'Поточний пароль',
  quantity: 'Кількість',
  note: 'Примітка',
  trip_id: 'Поїздка',
  category_id: 'Категорія',
}

// Якщо поля немає в словнику — беремо останній сегмент loc і робимо першу літеру великою.
function fieldLabel(loc) {
  const raw = Array.isArray(loc) ? loc[loc.length - 1] : loc
  if (FIELD_LABELS[raw]) return FIELD_LABELS[raw]
  const s = String(raw)
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : 'поле'
}

function cleanMsg(msg) {
  if (!msg) return ''
  return msg.replace(/^Value error,\s*/i, '').replace(/^Assertion failed,\s*/i, '')
}

// Перетворює один обʼєкт помилки валідації Pydantic v2 у зрозумілий український текст.
function validationMessage(err) {
  const field = fieldLabel(err && err.loc)
  const ctx = (err && err.ctx) || {}
  if (err && err.type === 'value_error') {
    return cleanMsg(err.msg) || 'Невірне значення'
  }
  switch (err && err.type) {
    case 'missing':
      return `Поле «${field}» обов'язкове`
    case 'string_too_short':
      return `«${field}» має містити щонайменше ${ctx.min_length} символів`
    case 'string_too_long':
      return `«${field}» має містити не більше ніж ${ctx.max_length} символів`
    case 'string_pattern_mismatch':
      return `«${field}» містить недопустимі символи`
    case 'int_type':
    case 'int_parsing':
      return `«${field}» має бути цілим числом`
    case 'greater_than_equal':
      return `«${field}» має бути не менше ${ctx.ge}`
    case 'less_than_equal':
      return `«${field}» має бути не більше ${ctx.le}`
    default:
      return err && err.msg ? `«${field}»: ${cleanMsg(err.msg)}` : `Помилка валідації поля «${field}»`
  }
}

function formatApiError(status, data) {
  const detail = data && data.detail

  if (typeof detail === 'string' && detail) return detail

  if (Array.isArray(detail) && detail.length > 0) {
    if (status === 422) {
      return detail.slice(0, 2).map(validationMessage).join(', ')
    }
    return detail.map(e => (e && e.msg) || '').filter(Boolean).join(', ')
  }

  return 'Щось пішло не так'
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
      auth.clearSession()
      throw new Error(data?.detail || 'Невірний логін або пароль')
    }

    handleUnauthorized()
    throw new Error('Сесія закінчилась. Будь ласка, увійдіть знову.')
  }

  if (res.status === 204) return null

  const data = await res.json().catch(() => null)

  if (!res.ok) {
    const error = new Error(formatApiError(res.status, data))
    error.status = res.status
    throw error
  }

  return data
}

export default {
  get: (endpoint) => request(endpoint),
  post: (endpoint, body) => request(endpoint, { method: 'POST', body }),
  patch: (endpoint, body) => request(endpoint, { method: 'PATCH', body }),
  delete: (endpoint, body) => request(endpoint, { method: 'DELETE', body }),
  // /login приймає дані у форматі x-www-form-urlencoded (OAuth2), тому form: true.
  // public: true — щоб 401 тут означав «невірний пароль», а не «вийди з сесії».
  login: (username, password) => request('/login', {
    method: 'POST',
    form: true,
    public: true,
    body: new URLSearchParams({ username, password })
  })
}
