export const AVATAR_COLORS = [
  '#42b883', '#3498db', '#e74c3c', '#f39c12', '#9b59b6',
  '#1abc9c', '#e67e22', '#2ecc71', '#e84393', '#34495e',
  '#16a085', '#c0392b'
]

export const DEFAULT_AVATAR_COLOR = AVATAR_COLORS[0]

export function avatarBackground(color, seed) {
  if (color && AVATAR_COLORS.includes(color)) return color
  if (seed) {
    let hash = 0
    for (let i = 0; i < seed.length; i++) {
      hash = (hash * 31 + seed.charCodeAt(i)) >>> 0
    }
    return AVATAR_COLORS[hash % AVATAR_COLORS.length]
  }
  return DEFAULT_AVATAR_COLOR
}