<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  categories: { type: Array, required: true }
})

const emit = defineEmits(['add-item', 'create-category'])


const newItemName = ref('')
const selectedCategoryId = ref('')
const newCategoryName = ref('')
const showCategoryForm = ref(false)


watch(() => props.categories, (newCats) => {
  if (newCats && newCats.length > 0 && !selectedCategoryId.value) {
    selectedCategoryId.value = newCats[0].id
  }
}, { immediate: true })

const submitItem = () => {
  if (!newItemName.value.trim() || !selectedCategoryId.value) return
  
  emit('add-item', {
    name: newItemName.value,
    categoryId: selectedCategoryId.value
  })
  
  newItemName.value = '' 
}

const submitCategory = () => {
  if (!newCategoryName.value.trim()) return
  
  emit('create-category', newCategoryName.value)
  
  newCategoryName.value = '' 
  showCategoryForm.value = false 
}
</script>

<template>
  <div class="add-item-card">
    <h3>Додати річ у список</h3>
    
    <form @submit.prevent="submitItem" class="item-form">
      <input type="text" v-model="newItemName" placeholder="Назва речі (напр., Намет)" required />
      <select v-model="selectedCategoryId">
        <option v-for="cat in categories" :key="cat.id" :value="cat.id">
          {{ cat.name }}
        </option>
      </select>
      <button type="submit">Додати</button>
    </form>

    <div class="category-toggle">
      <a href="#" @click.prevent="showCategoryForm = !showCategoryForm">
        {{ showCategoryForm ? 'Сховати' : '+ Створити нову категорію' }}
      </a>
    </div>
    
    <form v-if="showCategoryForm" @submit.prevent="submitCategory" class="category-form">
      <input type="text" v-model="newCategoryName" placeholder="Назва нової категорії (напр., Їжа)" required />
      <button type="submit" class="btn-secondary">Створити</button>
    </form>
  </div>
</template>

<style scoped>
.add-item-card {
  background: white;
  padding: 20px;
  border-radius: 10px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  margin-bottom: 20px;
}
.item-form {
  display: flex;
  gap: 10px;
}
.item-form input, .item-form select {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 5px;
  font-size: 14px;
}
.item-form input {
  flex: 1;
}
.item-form button {
  background-color: #42b883;
  color: white;
  border: none;
  padding: 8px 15px;
  border-radius: 5px;
  font-weight: bold;
  cursor: pointer;
}
.category-toggle {
  margin-top: 10px;
  font-size: 13px;
}
.category-toggle a {
  color: #3498db;
  text-decoration: none;
}
.category-form {
  display: flex;
  gap: 10px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #eee;
}
.category-form input {
  flex: 1;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 5px;
}
.btn-secondary {
  background-color: #95a5a6;
  color: white;
  border: none;
  padding: 8px 15px;
  border-radius: 5px;
  cursor: pointer;
}
</style>