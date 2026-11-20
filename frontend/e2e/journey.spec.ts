import { test, expect, type Page } from '@playwright/test'

async function demo(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Explore the demo' }).click()
  await expect(page.getByRole('heading', { name: 'A little progress, every day.' })).toBeVisible()
}
async function navigate(page: Page, name: string) {
  const toggle = page.getByRole('button', { name: 'Open navigation', exact: true })
  if (await toggle.isVisible()) await toggle.click()
  await page.getByRole('link', { name, exact: true }).first().click()
}
test('review, prepare, report submission, follow up, and schedule an interview', async ({
  page,
}) => {
  const employerRequests: string[] = []
  page.on('request', (req) => {
    if (req.url().startsWith('https://example.com')) employerRequests.push(req.url())
  })
  await demo(page)
  await navigate(page, 'Shortlists')
  await page.getByRole('button', { name: 'Create shortlist' }).click()
  await page.getByRole('checkbox', { name: 'Select Product Engineer', exact: true }).check()
  await page.getByRole('button', { name: 'Approve 1 selected' }).click()
  await page.getByRole('button', { name: 'Confirm approval' }).click()
  await page.getByRole('button', { name: 'Create draft', exact: true }).click()
  await page
    .getByRole('textbox', { name: 'Cover letter', exact: true })
    .fill(
      'Hello Fieldwork team, I would like to apply for this role. My React and Python experience is described in my profile. I would welcome a conversation.',
    )
  await page.getByRole('button', { name: 'Save revision' }).click()
  await expect(page.getByText('Revision 2 saved.', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Mark ready', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Confirm status change' })).toBeDisabled()
  await page
    .getByRole('checkbox', { name: 'I reviewed the cover letter and resume details.' })
    .check()
  await page.getByRole('button', { name: 'Confirm status change' }).click()
  await page.getByRole('button', { name: 'Prepare Manual Handoff', exact: true }).click()
  await page
    .getByRole('checkbox', { name: 'I reviewed the cover letter and resume details.' })
    .check()
  await page
    .getByRole('checkbox', { name: 'I understand I must open the employer site and apply myself.' })
    .check()
  await page.getByRole('button', { name: 'Confirm preparation' }).click()
  await expect(page.getByText(/Prepared — open the employer site/)).toBeVisible()
  await page.getByRole('button', { name: 'I submitted this application', exact: true }).click()
  await page
    .getByRole('checkbox', { name: 'I confirm I completed submission on the employer site.' })
    .check()
  await page.getByRole('button', { name: 'Confirm status change' }).click()
  await expect(
    page.getByText('Recorded your submission report. No employer confirmation was received.'),
  ).toBeVisible()
  await navigate(page, 'Follow-ups')
  await page.getByRole('button', { name: 'Schedule follow-up', exact: true }).click()
  await page
    .getByRole('combobox', { name: 'Application', exact: true })
    .selectOption({ label: 'Product Engineer' })
  await page.getByLabel('When', { exact: true }).fill('2027-01-20T12:00')
  await page.getByLabel('Note', { exact: true }).fill('Check the application status.')
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Schedule follow-up', exact: true })
    .click()
  await expect(page.getByText('Follow-up scheduled. No message has been sent.')).toBeVisible()
  await navigate(page, 'Interviews')
  await page.getByRole('button', { name: 'Schedule interview', exact: true }).click()
  await page
    .getByRole('combobox', { name: 'Application', exact: true })
    .selectOption({ label: 'Product Engineer' })
  await page.getByLabel('Interview title', { exact: true }).fill('Product conversation')
  await page.getByLabel('Start', { exact: true }).fill('2027-01-22T10:00')
  await page.getByLabel('End', { exact: true }).fill('2027-01-22T11:00')
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Schedule interview', exact: true })
    .click()
  await expect(page.getByRole('heading', { name: 'Product conversation' })).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download .ics' }).click()
  expect((await download).suggestedFilename()).toBe('interview.ics')
  await navigate(page, 'Notifications')
  await expect(page.getByRole('heading', { name: 'Scheduled for later' })).toBeVisible()
  expect(employerRequests).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
})
test('resume validation, profile correction, search URL state, and sign-out', async ({ page }) => {
  await demo(page)
  await navigate(page, 'Your profile')
  await page.getByLabel('Full name', { exact: true }).fill('Sam Example')
  await page.getByRole('button', { name: 'Save profile', exact: true }).click()
  await expect(page.getByText('Profile saved for this demo visit.')).toBeVisible()
  await page.getByRole('link', { name: 'Review a resume' }).click()
  await page
    .getByLabel('Choose resume file')
    .setInputFiles({ name: 'resume.txt', mimeType: 'text/plain', buffer: Buffer.from('invalid') })
  await expect(page.getByText('Choose a PDF or DOCX file.')).toBeVisible()
  await page.getByRole('button', { name: 'Open sample review' }).click()
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: 'Import approved sample skills' }).click()
  await expect(page.getByRole('button', { name: 'Import approved sample skills' })).toBeDisabled()
  await navigate(page, 'Discover jobs')
  await page.getByRole('textbox', { name: 'Search jobs' }).fill('React Developer')
  await expect(page).toHaveURL(/q=React/)
  await expect(page.getByRole('heading', { name: 'React Developer' })).toBeVisible()
  await page.getByRole('textbox', { name: 'Search jobs' }).fill('nonexistent role')
  await expect(page.getByRole('heading', { name: 'No roles found' })).toBeVisible()
  const toggle = page.getByRole('button', { name: 'Open navigation', exact: true })
  if (await toggle.isVisible()) await toggle.click()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await page.goto('/profile')
  await expect(page).toHaveURL(/login/)
})
