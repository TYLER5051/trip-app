import { createRouter, createWebHistory } from 'vue-router'
import App from '../App.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/HomeView.vue')
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue')
  },
  {
    path: '/trips/:id',
    name: 'TripDetail',
    component: () => import('../views/TripDetailView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const isAuthenticated = !!localStorage.getItem('access_token')

  if (!isAuthenticated && to.name !== 'Login') {
    next({ name: 'Login' }) 
  } 

  else if (isAuthenticated && to.name === 'Login') {
    next({ name: 'Home' })
  } 
  else {
    next() 
  }
})

export default router