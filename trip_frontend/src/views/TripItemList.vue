<script setup>
const props = defineProps({
  groupedItems: { type: Object, required: true },
  currentUser: { type: String, required: true },
  ownerUsername: { type: String, required: false }
})

const emit = defineEmits(['toggle', 'delete'])
</script>

<template>
  <div class="items-section">
    <h3>Список речей</h3>
    
    <!-- Якщо немає жодної категорії в згрупованих речах, значить список порожній -->
    <div v-if="Object.keys(groupedItems).length === 0" class="empty">
      У цій поїздці поки немає жодної речі.
    </div>
    
    <div v-else>
      <div v-for="(items, categoryName) in groupedItems" :key="categoryName" class="category-group">
        <h4 class="category-title"> {{ categoryName }}</h4>
        <ul class="items-list">
          <li v-for="item in items" :key="item.id" class="item-row">
            
            <!-- Ліва частина речі (чекбокс і ім'я) -->
            <div class="item-content">
              <label class="item-label">
                <input 
                  type="checkbox" 
                  :checked="!!item.assigned_user" 
                  @change="emit('toggle', item)"
                  :disabled="!!item.assigned_user && item.assigned_user.username !== currentUser && ownerUsername !== currentUser" 
                />
                <span class="item-name" :class="{ assigned: !!item.assigned_user }">
                  {{ item.name }}
                </span>
              </label>
              
              <span v-if="item.assigned_user" class="assignee-badge">
                Взяв(ла): {{ item.assigned_user.username }}
              </span>
            </div>

            <!-- Кнопка видалення (ТІЛЬКИ ДЛЯ ОРГАНІЗАТОРА) -->
            <button 
              v-if="ownerUsername === currentUser" 
              @click="emit('delete', item.id)" 
              class="delete-item-btn"
              title="Видалити річ"
            >
              ❌
            </button>
            
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.items-section {
  background: white;
  padding: 20px;
  border-radius: 10px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}
.category-group {
  margin-bottom: 20px;
}
.category-title {
  background-color: #f8f9fa;
  padding: 8px 12px;
  border-radius: 6px;
  color: #2c3e50;
  margin: 0 0 10px 0;
  font-size: 15px;
  border-left: 4px solid #42b883;
}
.items-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.item-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #eee;
}
.item-row:last-child {
  border-bottom: none;
}
.item-label {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}
.item-label input[type="checkbox"] {
  width: 20px;
  height: 20px;
  cursor: pointer;
  accent-color: #27ae60;
}
.item-name {
  font-size: 16px;
  font-weight: 500;
  transition: all 0.2s ease;
}
.item-name.assigned {
  text-decoration: line-through;
  color: #95a5a6;
}
.assignee-badge {
  background-color: #e8f4f8;
  color: #2980b9;
  padding: 4px 12px;
  border-radius: 15px;
  font-size: 13px;
  font-weight: bold;
}
.empty {
  text-align: center;
  color: #666;
  margin-top: 20px;
}
.item-content { 
  display: flex; 
  align-items: center; 
  gap: 12px; 
  flex: 1; 
}
.delete-item-btn { 
  background: none; 
  border: none; 
  font-size: 16px; 
  cursor: pointer; 
  opacity: 0.5; 
  transition: opacity 0.2s; 
  padding: 4px; 
}
.delete-item-btn:hover { 
  opacity: 1; 
}
</style>