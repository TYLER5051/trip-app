export const AVATAR_COLORS = [
  '#42b883', '#3498db', '#e74c3c', '#f39c12', '#9b59b6',
  '#1abc9c', '#e67e22', '#2ecc71', '#e84393', '#34495e',
  '#16a085', '#c0392b'
]

export const DEFAULT_AVATAR_COLOR = AVATAR_COLORS[0]

export function avatarBackground(color) {
  return color && AVATAR_COLORS.includes(color) ? color : DEFAULT_AVATAR_COLOR
}