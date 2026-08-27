const API_URL = 'http://localhost:8000'

async function request(endpoint, options = {}) {
  const token = localStorage.getItem('access_token')
  
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await `${API_URL}${endpoint}`
}