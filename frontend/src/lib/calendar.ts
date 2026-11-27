import type { Interview } from './demo'
const escape = (value: string) =>
  value.replace(/\\/g, '\\\\').replace(/\r?\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;')
const stamp = (value: string) =>
  new Date(value)
    .toISOString()
    .replace(/[-:]/g, '')
    .replace(/\.\d{3}/, '')
export function calendar(i: Interview): string {
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Job Agent//Demo Interview//EN',
    'CALSCALE:GREGORIAN',
    'BEGIN:VEVENT',
    `UID:${i.id}@demo.jobagent`,
    `DTSTAMP:${stamp(new Date().toISOString())}`,
    `DTSTART:${stamp(i.start)}`,
    `DTEND:${stamp(i.end)}`,
    `SUMMARY:${escape(i.title)}`,
    `LOCATION:${escape(i.location)}`,
    'END:VEVENT',
    'END:VCALENDAR',
  ]
  // RFC 5545 folds at 75 octets, including the continuation space.
  const encoder = new TextEncoder()
  return (
    lines
      .flatMap((line) => {
        const folded: string[] = []
        let part = ''
        let bytes = 0
        for (const char of line) {
          const size = encoder.encode(char).length
          if (bytes + size > 75) {
            folded.push(part)
            part = ' '
            bytes = 1
          }
          part += char
          bytes += size
        }
        folded.push(part)
        return folded
      })
      .join('\r\n') + '\r\n'
  )
}
export function downloadCalendar(i: Interview) {
  const url = URL.createObjectURL(new Blob([calendar(i)], { type: 'text/calendar;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = 'interview.ics'
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export function localInput(value: string) {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
