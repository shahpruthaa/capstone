import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseUrl = 'http://127.0.0.1:3001';
const outDir = path.resolve('tmp', 'ui-smoke');

async function saveShot(page, name) {
  await fs.mkdir(outDir, { recursive: true });
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true });
}

async function textContentOrEmpty(locator) {
  try {
    const text = await locator.textContent({ timeout: 10000 });
    return (text || '').trim();
  } catch {
    return '';
  }
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(60000);

  const outcome = {
    generate: {},
    analyze: {},
    backtest: {},
    compare: {},
    aiChat: {},
    screenshotsDir: outDir,
  };

  try {
    await page.goto(baseUrl, { waitUntil: 'load' });
    await page.getByRole('button', { name: 'Generate' }).waitFor();

    // GENERATE
    await page.getByRole('button', { name: 'Generate', exact: true }).click();
    await page.locator('input[type="number"]').first().fill('500000');
    await page.getByRole('button', { name: /Balanced/i }).click();
    await page.getByRole('button', { name: /Generate AI Portfolio/i }).click();
    await page.getByText('Stock Allocation').waitFor();

    const generateRuntimeCard = page.locator('.card').filter({ hasText: 'Model Runtime' }).first();
    outcome.generate.modelRuntime = await textContentOrEmpty(generateRuntimeCard);
    outcome.generate.backendNotesVisible = await page.getByText('Backend Model Notes').isVisible().catch(() => false);

    const aiButton = page.getByRole('button', { name: /Generate AI Analysis|Regenerate AI Analysis/i });
    await aiButton.click();
    await page.waitForTimeout(4000);
    const insightText = await textContentOrEmpty(page.locator('.card').filter({ hasText: 'AI Portfolio Analysis' }).first());
    outcome.generate.aiInsightSnippet = insightText.slice(0, 300);

    await saveShot(page, '01-generate');

    // ANALYZE
    await page.getByRole('button', { name: 'Analyze' }).click();
    await page.locator('textarea').first().fill('INFY 10\nTCS 5\nHDFCBANK 8');
    await page.getByRole('button', { name: 'Analyze Pasted Portfolio' }).click();
    await page.getByText('Portfolio Value').waitFor();

    outcome.analyze.modelRuntime = await textContentOrEmpty(page.locator('.card').filter({ hasText: 'Model Runtime' }).first());
    outcome.analyze.topSuggestion = await textContentOrEmpty(page.locator('.alert-warning, .alert-success').first());

    await saveShot(page, '02-analyze');

    // BACKTEST
    await page.getByRole('button', { name: 'Backtest' }).click();
    await page.getByRole('button', { name: /Run Backtest/i }).click();
    await page.getByText('Prediction Validation Snapshot').waitFor({ timeout: 120000 });

    outcome.backtest.modelRuntime = await textContentOrEmpty(page.locator('.card').filter({ hasText: 'Model Runtime' }).first());
    outcome.backtest.totalReturn = await textContentOrEmpty(page.locator('.card').filter({ hasText: 'Total Return' }).first());
    outcome.backtest.validationCard = await textContentOrEmpty(page.locator('.card').filter({ hasText: 'Prediction Validation Snapshot' }).first());

    await saveShot(page, '03-backtest');

    // COMPARE
    await page.getByRole('button', { name: 'Compare' }).click();
    await page.getByText('Industry Benchmark Comparison').waitFor({ timeout: 120000 });
    let compareLoaded = false;
    try {
      await page.locator('table.data-table tbody tr').first().waitFor({ timeout: 30000 });
      compareLoaded = true;
    } catch {
      compareLoaded = false;
    }

    outcome.compare.header = await textContentOrEmpty(page.locator('.card').filter({ hasText: 'Industry Benchmark Comparison' }).first());
    outcome.compare.loaded = compareLoaded;
    if (!compareLoaded) {
      outcome.compare.errorNotice = await textContentOrEmpty(page.locator('.alert-warning').filter({ hasText: 'Benchmark comparison failed' }).first());
    }
    outcome.compare.firstRows = [];
    if (compareLoaded) {
      const rows = page.locator('table.data-table tbody tr');
      const count = Math.min(await rows.count(), 3);
      for (let i = 0; i < count; i += 1) {
        outcome.compare.firstRows.push((await textContentOrEmpty(rows.nth(i))).replace(/\s+/g, ' ').trim());
      }
    }

    await saveShot(page, '04-compare');

    // AI CHAT
    await page.getByRole('button', { name: 'AI Strategy Assistant' }).click();
    await page.getByPlaceholder('Ask about stocks, taxes, strategy...').fill('Give me a 2-line summary of this portfolio risk and one action item.');
    await page.locator('.chat-window button.btn-primary').click();

    await page.waitForFunction(() => {
      const aiBubbles = Array.from(document.querySelectorAll('.chat-window .bg-slate-100.rounded-2xl'));
      return aiBubbles.some((node) => {
        const text = (node.textContent || '').trim();
        return text.length > 40 && !text.includes("Hi! I'm your NSE AI Portfolio Assistant");
      });
    }, { timeout: 120000 });

    const aiBubbles = page.locator('.chat-window .bg-slate-100.rounded-2xl');
    const aiCount = await aiBubbles.count();
    let resolvedReply = '';
    for (let i = aiCount - 1; i >= 0; i -= 1) {
      const text = await textContentOrEmpty(aiBubbles.nth(i));
      if (text.length > 40 && !text.includes("Hi! I'm your NSE AI Portfolio Assistant")) {
        resolvedReply = text;
        break;
      }
    }
    outcome.aiChat.lastReplySnippet = resolvedReply.slice(0, 350);

    await saveShot(page, '05-ai-chat');

    console.log(JSON.stringify(outcome, null, 2));
  } catch (error) {
    await fs.mkdir(outDir, { recursive: true });
    await page.screenshot({ path: path.join(outDir, '00-failure.png'), fullPage: true });
    throw error;
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error('SMOKE_TEST_FAILED');
  console.error(error?.stack || String(error));
  process.exit(1);
});
