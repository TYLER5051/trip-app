<script setup>
import { ref, nextTick, computed } from 'vue'

const props = defineProps({
  groupedItems: { type: Object, required: true },
  categories: { type: Array, required: true },
  currentUser: { type: String, required: true },
  ownerUsername: { type: String, required: false }
})

const emit = defineEmits(['toggle', 'delete', 'rename', 'update-quantity', 'unmark-critical', 'rename-category', 'delete-category'])

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

// Чи «взяв» річ поточний користувач (його чекбокс)
const assignedByMe = (item) => item.assigned_users && item.assigned_users.some(a => a.username === props.currentUser)

// Всі місця (quantity) уже розібрані
const itemFull = (item) => !!(item.assigned_users && item.assigned_users.length >= item.quantity)

// Фільтри списку речей
const showOnlyFree = ref(false)
const showMyItems = ref(false)
const sortByStatus = ref('free-first')

// Відфільтровані/відсортовані речі (в межах кожної категорії)
const filteredGroups = computed(() => {
  const result = {}

  Object.entries(props.groupedItems).forEach(([categoryName, items]) => {
    let list = items

    if (showOnlyFree.value) {
      list = list.filter(item => !item.assigned_users || item.assigned_users.length === 0)
    }

    if (showMyItems.value) {
      list = list.filter(item =>
        (item.created_by && item.created_by.username === props.currentUser) ||
        assignedByMe(item)
      )
    }

    if (sortByStatus.value !== 'none') {
      const freeFirst = sortByStatus.value === 'free-first'
      list = [...list].sort((a, b) => {
        const aFree = !a.assigned_users || a.assigned_users.length === 0 ? 1 : 0
        const bFree = !b.assigned_users || b.assigned_users.length === 0 ? 1 : 0
        return freeFirst ? bFree - aFree : aFree - bFree
      })
    }

    if (list.length) result[categoryName] = list
  })

  return result
})

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
      <div class="item-filters">
        <label class="filter-check">
          <input type="checkbox" v-model="showOnlyFree" />
          Показати тільки невзяті
        </label>
        <label class="filter-check">
          <input type="checkbox" v-model="showMyItems" />
          Мої речі
        </label>
        <label class="filter-sort">
          <select v-model="sortByStatus" class="filter-select">
            <option value="free-first">Невзяті зверху</option>
            <option value="packed-first">Взяті зверху</option>
            <option value="none">Сортування: за замовчуванням</option>
          </select>
        </label>
      </div>

      <div v-if="Object.keys(filteredGroups).length === 0" class="empty">
        За вибраними фільтрами речей не знайдено.
      </div>

      <div v-for="(items, categoryName) in filteredGroups" :key="categoryName" class="category-group">
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
                  :checked="assignedByMe(item)"
                  @change="emit('toggle', item)"
                  :disabled="!assignedByMe(item) && itemFull(item)"
                  :title="!assignedByMe(item) && itemFull(item) ? 'Всі місця розібрані' : ''"
                />
                <span class="item-info">
                  <span class="item-name" :class="{ assigned: assignedByMe(item) }">
                    {{ item.name }}
                    <span v-if="item.quantity && item.quantity > 1" class="qty-badge" title="Кількість">×{{ item.quantity }}</span>
                  </span>
                  <span v-if="item.note" class="item-note">{{ item.note }}</span>
                </span>
                <button
                  v-if="item.is_critical && canModifyItem(item)"
                  class="critical-badge clickable"
                  title="Зняти мітку «Важлива» (після цього можна видалити)"
                  @click="emit('unmark-critical', item)"
                >⭐</button>
                <span v-else-if="item.is_critical" class="critical-badge" title="Важлива річ">⭐</span>
              </label>

              <span v-if="item.created_by" class="creator-badge">
                Автор: {{ item.created_by.username }}
              </span>
              <span v-if="item.assigned_users && item.assigned_users.length" class="assignee-badge">
                Бере: {{ item.assigned_users.map(a => a.username).join(', ') }}
              </span>
              <span v-if="item.quantity > 1" class="taken-count" :class="{ full: itemFull(item) }">
                {{ item.assigned_users ? item.assigned_users.length : 0 }}/{{ item.quantity }}
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
              <input
                type="number"
                min="1"
                class="qty-edit"
                :value="item.quantity"
                title="Змінити кількість (шт)"
                @change="emit('update-quantity', { id: item.id, quantity: $event.target.value })"
              />
            </div>

            <!-- Кнопка видалення: для організатора або автора речі (важливу — спершу зняти мітку) -->
            <button
              v-if="canModifyItem(item)"
              @click="emit('delete', item.id)"
              class="delete-item-btn"
              :title="item.is_critical ? 'Важливу річ не можна видалити. Спочатку зніміть мітку «Важлива».' : 'Видалити річ'"
              :disabled="item.is_critical"
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
.item-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 15px;
  background: #f8f9fa;
  padding: 10px 14px;
  border-radius: 8px;
  margin-bottom: 16px;
}
.filter-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #34495e;
  cursor: pointer;
}
.filter-check input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: #42b883;
}
.filter-select {
  padding: 5px 8px;
  border: 1px solid #d5dbe1;
  border-radius: 5px;
  font-size: 13px;
  color: #34495e;
  background: white;
  cursor: pointer;
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
.item-info {
  display: flex;
  flex-direction: column;
}
.qty-badge {
  background-color: #e8f5e9;
  color: #27ae60;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: bold;
  margin-left: 6px;
}
.critical-badge {
  font-size: 14px;
  margin-left: 6px;
  background: none;
  border: none;
  padding: 0;
}
.critical-badge.clickable {
  cursor: pointer;
  opacity: 0.85;
}
.critical-badge.clickable:hover {
  opacity: 1;
  transform: scale(1.15);
}
.item-note {
  font-size: 12px;
  color: #95a5a6;
  margin-top: 2px;
}
.qty-edit {
  width: 52px;
  padding: 3px 6px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
}
.qty-edit:focus {
  outline: none;
  border-color: #42b883;
}
.taken-count {
  font-size: 12px;
  color: #2980b9;
  font-weight: bold;
  margin-left: 6px;
}
.taken-count.full {
  color: #27ae60;
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
