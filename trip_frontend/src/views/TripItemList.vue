<script setup>
import { ref, nextTick } from 'vue'

const props = defineProps({
  groupedItems: { type: Object, required: true },
  categories: { type: Array, required: true },
  currentUser: { type: String, required: true },
  ownerUsername: { type: String, required: false }
})

const emit = defineEmits(['toggle', 'delete', 'rename', 'rename-category', 'delete-category'])

// Стан редагування назви речі
const editingId = ref(null)
const draftName = ref('')
const renameInput = ref(null)

// Стан редагування назви категорії
const editingCategoryId = ref(null)
const categoryDraftName = ref('')
const categoryRenameInput = ref(null)

// Право на перейменування/видалення має організатор або автор речі (не той, хто взяв)
const canModifyItem = (item) => {
  const isOwner = props.ownerUsername === props.currentUser
  const isCreator = item.created_by && item.created_by.username === props.currentUser
  return isOwner || isCreator
}

// Знайти об'єкт категорії за назвою групи (назви унікальні в межах поїздки)
const catFor = (name) => props.categories.find(c => c.name === name)

// Категорію (як і річ) може змінювати/видаляти лише її автор або організатор
const canModifyCategory = (cat) => {
  if (!cat) return false
  const isOwner = props.ownerUsername === props.currentUser
  const isCreator = cat.created_by && cat.created_by.username === props.currentUser
  return isOwner || isCreator
}

const isEditing = (item) => editingId.value === item.id

const startRename = async (item) => {
  draftName.value = item.name
  editingId.value = item.id
  await nextTick()
  renameInput.value?.focus()
}

const cancelRename = () => {
  editingId.value = null
  draftName.value = ''
}

const saveRename = (item) => {
  const trimmed = draftName.value.trim()
  if (!trimmed) {
    cancelRename()
    return
  }
  if (trimmed !== item.name) {
    emit('rename', { id: item.id, name: trimmed })
  }
  cancelRename()
}

const isCategoryEditing = (cat) => editingCategoryId.value === cat.id

const startCategoryRename = async (cat) => {
  categoryDraftName.value = cat.name
  editingCategoryId.value = cat.id
  await nextTick()
  categoryRenameInput.value?.focus()
}

const cancelCategoryRename = () => {
  editingCategoryId.value = null
  categoryDraftName.value = ''
}

const saveCategoryRename = (cat) => {
  const trimmed = categoryDraftName.value.trim()
  if (!trimmed) {
    cancelCategoryRename()
    return
  }
  if (trimmed !== cat.name) {
    emit('rename-category', { id: cat.id, name: trimmed })
  }
  cancelCategoryRename()
}
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
        <div class="category-header">
          <h4 class="category-title"> {{ categoryName }}</h4>
          <div v-if="catFor(categoryName)" class="category-actions">
            <template v-if="isCategoryEditing(catFor(categoryName))">
              <input
                ref="categoryRenameInput"
                v-model="categoryDraftName"
                type="text"
                class="rename-input"
                placeholder="Нова назва..."
                @keyup.enter="saveCategoryRename(catFor(categoryName))"
                @keyup.esc="cancelCategoryRename"
              />
              <button
                class="cat-action save"
                title="Зберегти"
                @click="saveCategoryRename(catFor(categoryName))"
              >✓</button>
              <button
                class="cat-action cancel"
                title="Скасувати"
                @click="cancelCategoryRename"
              >✕</button>
            </template>
            <template v-else>
              <button
                v-if="canModifyCategory(catFor(categoryName))"
                class="cat-action"
                title="Перейменувати категорію"
                @click="startCategoryRename(catFor(categoryName))"
              >✏️</button>
              <button
                v-if="canModifyCategory(catFor(categoryName))"
                class="cat-action"
                title="Видалити категорію"
                @click="emit('delete-category', catFor(categoryName))"
              >❌</button>
            </template>
          </div>
        </div>
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

              <span v-if="item.created_by" class="creator-badge">
                Автор: {{ item.created_by.username }}
              </span>
              <span v-if="item.assigned_user" class="assignee-badge">
                Взяв(ла): {{ item.assigned_user.username }}
              </span>
            </div>

            <!-- Блок перейменування: для організатора або автора речі -->
            <div v-if="canModifyItem(item)" class="rename-section">
              <div v-if="isEditing(item)" class="rename-editor">
                <input
                  ref="renameInput"
                  v-model="draftName"
                  type="text"
                  class="rename-input"
                  placeholder="Нова назва..."
                  @keyup.enter="saveRename(item)"
                  @keyup.esc="cancelRename"
                />
                <button
                  class="rename-action save"
                  title="Зберегти"
                  @click="saveRename(item)"
                >✓</button>
                <button
                  class="rename-action cancel"
                  title="Скасувати"
                  @click="cancelRename"
                >✕</button>
              </div>
              <button
                v-else
                class="rename-action"
                title="Перейменувати"
                @click="startRename(item)"
              >✏️</button>
            </div>

            <!-- Кнопка видалення: для організатора або автора речі -->
            <button
              v-if="canModifyItem(item)"
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
.category-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.category-actions {
  display: flex;
  gap: 4px;
  margin-left: auto;
}
.cat-action {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  padding: 4px 6px;
  border-radius: 4px;
  opacity: 0.6;
  transition: opacity 0.2s, background-color 0.2s;
}
.cat-action:hover {
  opacity: 1;
  background-color: #e2e6ea;
}
.cat-action.save {
  color: #27ae60;
  font-weight: bold;
}
.cat-action.cancel {
  color: #e74c3c;
  font-weight: bold;
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
.creator-badge {
  background-color: #fdf2e3;
  color: #b9770e;
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
.rename-section {
  margin-left: auto;
  margin-right: 8px;
  display: flex;
  align-items: center;
}
.rename-editor {
  display: flex;
  align-items: center;
  gap: 4px;
}
.rename-action {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  padding: 4px 6px;
  border-radius: 4px;
  opacity: 0.6;
  transition: opacity 0.2s, background-color 0.2s;
}
.rename-action:hover {
  opacity: 1;
  background-color: #eef2f5;
}
.rename-action.save {
  color: #27ae60;
  font-weight: bold;
}
.rename-action.cancel {
  color: #e74c3c;
  font-weight: bold;
}
.rename-input {
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  width: 150px;
}
.rename-input:focus {
  outline: none;
  border-color: #42b883;
}
</style>
