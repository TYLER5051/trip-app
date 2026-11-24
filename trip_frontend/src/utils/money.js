// Форматування грошових сум бюджету поїздки.
// API віддає суми рядками ("1234.50") — нормалізуємо через Number.
const nf = new Intl.NumberFormat('uk-UA', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
})

export function formatMoney(value, currency = '₴') {
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return `${nf.format(num)} ${currency}`.trim()
}

// Перетворення введеної суми у рядок із двома знаками після коми (для запитів до API).
export function toDecimalString(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '0.00'
  return num.toFixed(2)
}
