<script setup>
import { computed } from 'vue'
import { avatarBackground } from '../utils/avatar'

const props = defineProps({
  username: { type: String, required: false, default: '' },
  color: { type: String, required: false, default: null },
  size: { type: Number, required: false, default: 40 }
})

const letter = computed(() => (props.username?.[0] || '?').toUpperCase())
const background = computed(() => avatarBackground(props.color))
</script>

<template>
  <div
    class="user-avatar"
    :style="{
      width: size + 'px',
      height: size + 'px',
      fontSize: Math.round(size * 0.42) + 'px',
      background
    }"
  >
    {{ letter }}
  </div>
</template>

<style scoped>
.user-avatar {
  border-radius: 50%;
  color: white;
  font-weight: bold;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  user-select: none;
}
</style>