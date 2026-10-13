const priceFormatter = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

const dateFormatter = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
})

const timeFormatter = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' })

/** Formats a decimal amount sent by the API as text, for example "4.5" as "$4.50". */
export function formatPrice(price: string): string {
  return priceFormatter.format(Number(price))
}

/** Like formatPrice, but shows "Free" for a price of zero. */
export function formatPriceOrFree(price: string): string {
  return Number(price) === 0 ? 'Free' : formatPrice(price)
}

/** Formats an ISO calendar date such as "2026-06-01" as "Jun 1, 2026". */
export function formatDate(isoDate: string): string {
  // Built from its parts so the date is read as local. Parsing the string
  // directly would treat it as UTC and can show the previous day.
  const [year, month, day] = isoDate.split('-').map(Number)
  return dateFormatter.format(new Date(year, month - 1, day))
}

/** Formats a 24-hour time such as "14:30:00" as "2:30 PM". */
export function formatTime(time: string): string {
  const [hours, minutes] = time.split(':').map(Number)
  return timeFormatter.format(new Date(2000, 0, 1, hours, minutes))
}

const dateTimeFormatter = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

/** Formats a timestamp such as "2026-06-01T14:30:00Z" in the reader's own time zone. */
export function formatDateTime(timestamp: string): string {
  return dateTimeFormatter.format(new Date(timestamp))
}

export function formatDistance(miles: number): string {
  return `${miles.toFixed(1)} mi`
}

/** Today's date in the browser's time zone as an ISO calendar date, for date inputs. */
export function todayAsIsoDate(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}
