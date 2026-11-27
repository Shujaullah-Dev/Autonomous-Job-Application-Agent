import { chromium } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
await mkdir('../docs/frontend-screenshots', { recursive: true })
const browser = await chromium.launch()
for (const [name, width, height] of [
  ['desktop', 1440, 1050],
  ['mobile', 390, 844],
]) {
  const page = await browser.newPage({ viewport: { width, height } })
  await page.goto('http://127.0.0.1:5174/')
  await page.getByRole('button', { name: 'Explore the demo' }).click()
  await page.getByRole('heading', { name: 'A little progress, every day.' }).waitFor()
  await page.screenshot({
    path: `../docs/frontend-screenshots/dashboard-${name}.png`,
    fullPage: true,
  })
  console.log(
    `${name}: ${(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)) ? 'no horizontal overflow' : 'OVERFLOW'}`,
  )
  await page.close()
}
await browser.close()
