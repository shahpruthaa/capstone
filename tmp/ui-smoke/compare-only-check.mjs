import { chromium } from '@playwright/test';

const baseUrl = 'http://127.0.0.1:3001';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(120000);

const result = { green: false, reason: '' };

try {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Compare' }).click();
  await page.getByText('Industry Benchmark Comparison').waitFor({ timeout: 120000 });
  result.green = true;
  result.reason = 'Compare header visible';
} catch (error) {
  result.green = false;
  result.reason = String(error?.message || error);
} finally {
  await browser.close();
}

console.log(JSON.stringify(result, null, 2));
