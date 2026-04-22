import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseUrl = 'http://127.0.0.1:3000';
const outDir = path.resolve('tmp', 'ui-smoke');

async function ensureOutDir() {
  await fs.mkdir(outDir, { recursive: true });
}

async function saveShot(page, name) {
  await page.screenshot({ path: path.join(outDir, name), fullPage: true });
}

function parseNumberFromText(text) {
  const match = String(text || '').replace(/,/g, '').match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;
  return Number(match[0]);
}

async function run() {
  await ensureOutDir();

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(90000);

  const result = {
    compare: { pass: false, details: {} },
    market: { pass: false, details: {} },
    tradeIdeas: { pass: false, details: {} },
    screenshotsDir: outDir,
  };

  try {
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });

    // Compare tab smoke
    await page.getByRole('button', { name: 'Compare' }).click();
    await page.getByText('Mandate-Aware Benchmark Compare').waitFor({ timeout: 120000 });

    await page.waitForFunction(() => {
      const rows = document.querySelectorAll('table.data-table tbody tr').length;
      const body = document.body?.innerText || '';
      const hasError = body.includes('Compare service is unavailable');
      return rows > 0 || hasError;
    }, undefined, { timeout: 120000 });

    const compareRows = await page.locator('table.data-table tbody tr').count();
    const compareError = await page.getByText('Compare service is unavailable').isVisible().catch(() => false);
    result.compare.pass = compareRows > 0 && !compareError;
    result.compare.details = {
      rowCount: compareRows,
      compareError,
    };
    await saveShot(page, 'manual-compare.png');

    // Market tab smoke
    await page.getByRole('button', { name: 'Market' }).click();
    await page.getByText('Market Regime and Leadership').waitFor({ timeout: 120000 });

    await page.getByText('Sector Relative Strength', { exact: true }).waitFor({ timeout: 120000 });
    await page.locator('table.data-table tbody tr').first().waitFor({ timeout: 120000 });

    const sectorRows = await page.locator('table.data-table tbody tr').count();
    const dailyBarsRow = page.locator('.stat-row', { hasText: 'Daily Bars' }).first();
    const dailyBarsText = (await dailyBarsRow.textContent()) || '';
    const dailyBars = parseNumberFromText(dailyBarsText);
    result.market.pass = sectorRows > 0 && Number.isFinite(dailyBars) && dailyBars > 0;
    result.market.details = {
      sectorRows,
      dailyBars,
    };
    await saveShot(page, 'manual-market.png');

    // Build a portfolio first so Trade Ideas receives live portfolio context.
    await page.getByRole('button', { name: 'Portfolio' }).click();
    await page.getByRole('button', { name: 'Build Portfolio' }).click();
    await page.locator('input[type="number"]').first().fill('500000');
    await page.getByRole('button', { name: /Balanced/i }).click();
    await page.getByRole('button', { name: /Generate AI Portfolio/i }).click();

    await page.waitForFunction(() => {
      const bodyText = document.body?.innerText || '';
      const hasSuccess = bodyText.includes('Model Runtime');
      const hasFailure = bodyText.includes('Portfolio generation failed:');
      return hasSuccess || hasFailure;
    }, undefined, { timeout: 180000 });

    const generationFailed = await page.getByText(/Portfolio generation failed:/i).isVisible().catch(() => false);
    if (generationFailed) {
      const failureText = await page.getByText(/Portfolio generation failed:/i).first().textContent();
      throw new Error(`Portfolio generation failed before Trade Ideas validation: ${(failureText || '').trim()}`);
    }

    // Trade Ideas tab smoke
    await page.getByRole('button', { name: 'Trade Ideas' }).click();
    await page.getByText('Trade Ideas With Portfolio Context').waitFor({ timeout: 120000 });

    await page.waitForFunction(() => {
      const body = document.body?.innerText || '';
      const noIdeas = body.includes('No ideas cleared the current 7/10 threshold');
      const hasChecklist = body.includes('Checklist score');
      return noIdeas || hasChecklist;
    }, undefined, { timeout: 120000 });

    const noIdeas = await page.getByText('No ideas cleared the current 7/10 threshold').isVisible().catch(() => false);
    const ideaCards = await page.locator('.card h3').count();
    const checklistLabels = await page.getByText('Checklist score').count();

    result.tradeIdeas.pass = !noIdeas && ideaCards > 0 && checklistLabels > 0;
    result.tradeIdeas.details = {
      noIdeas,
      ideaCards,
      checklistLabels,
    };
    await saveShot(page, 'manual-trade-ideas.png');

    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    await saveShot(page, 'manual-smoke-failure.png');
    console.log(JSON.stringify(result, null, 2));
    throw error;
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error('MANUAL_BROWSER_SMOKE_FAILED');
  console.error(error?.stack || String(error));
  process.exit(1);
});
