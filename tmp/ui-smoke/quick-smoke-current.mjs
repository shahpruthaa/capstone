import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseUrl = 'http://127.0.0.1:3001';
const outDir = path.resolve('tmp', 'ui-smoke');

async function shot(page, name) {
  await fs.mkdir(outDir, { recursive: true });
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true });
}

async function textOrEmpty(locator) {
  try {
    return ((await locator.textContent({ timeout: 10000 })) || '').trim();
  } catch {
    return '';
  }
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(90000);

  const result = {
    generate: { green: false, reason: '' },
    analyze: { green: false, reason: '' },
    backtest: { green: false, reason: '' },
    compare: { green: false, reason: '' },
    aiChat: { green: false, reason: '' },
    details: {},
    screenshotsDir: outDir,
  };

  try {
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Portfolio' }).click();

    try {
      await page.getByRole('button', { name: 'Build Portfolio' }).click();
      await page.locator('input[type="number"]').first().fill('500000');
      await page.getByRole('button', { name: /Balanced/i }).click();
      await page.getByRole('button', { name: /Generate AI Portfolio/i }).click();

      await page.waitForFunction(() => {
        const hasSuccess = document.querySelectorAll('.data-table tbody tr').length > 0;
        const bodyText = document.body?.innerText || '';
        const hasFailure = bodyText.includes('Portfolio generation failed:');
        return hasSuccess || hasFailure;
      }, undefined, { timeout: 180000 });

      const generationFailed = await page.getByText(/Portfolio generation failed:/i).isVisible().catch(() => false);
      if (generationFailed) {
        const failureText = await textOrEmpty(page.getByText(/Portfolio generation failed:/i).first());
        throw new Error(`Generate flow failed: ${failureText}`);
      }

      await page.locator('.data-table tbody tr').first().waitFor({ timeout: 30000 });
      result.generate.green = true;
      result.generate.reason = 'Stock allocation rendered after generation';
      result.details.generateModelRuntime = await textOrEmpty(page.locator('.card').filter({ hasText: 'Model Runtime' }).first());
    } catch (error) {
      result.generate.green = false;
      result.generate.reason = String(error?.message || error);
    }
    await shot(page, 'quick-01-generate');

    try {
      await page.getByRole('button', { name: 'Analyze Holdings' }).click();
      await page.locator('textarea').first().fill('INFY 10\nTCS 5\nHDFCBANK 8');
      await page.getByRole('button', { name: 'Analyze Pasted Portfolio' }).click();
      await page.getByText('Portfolio Value').waitFor({ timeout: 120000 });
      result.analyze.green = true;
      result.analyze.reason = 'Portfolio value metric rendered';
      result.details.analyzeTopBanner = await textOrEmpty(page.locator('p.text-xs.text-slate-500').first());
    } catch (error) {
      result.analyze.green = false;
      result.analyze.reason = String(error?.message || error);
    }
    await shot(page, 'quick-02-analyze');

    try {
      await page.getByRole('button', { name: 'Backtest' }).click();

      await page.waitForFunction(() => {
        const runButton = Array.from(document.querySelectorAll('button')).find((button) =>
          /Run Backtest/i.test(button.textContent || '')
        );
        return !!runButton && !runButton.hasAttribute('disabled');
      }, undefined, { timeout: 120000 });

      await page.getByRole('button', { name: /Run Backtest/i }).click();
      await page.getByText('Model Runtime').waitFor({ timeout: 180000 });
      await page.getByText('Total Return').waitFor({ timeout: 180000 });
      result.backtest.green = true;
      result.backtest.reason = 'Backtest metrics and runtime cards rendered';
      result.details.backtestTotalReturn = await textOrEmpty(page.locator('.card').filter({ hasText: 'Total Return' }).first());
    } catch (error) {
      result.backtest.green = false;
      result.backtest.reason = String(error?.message || error);
    }
    await shot(page, 'quick-03-backtest');

    try {
      await page.getByRole('button', { name: 'Compare' }).click();
      await page.getByText('Industry Benchmark Comparison').waitFor({ timeout: 120000 });
      await page.waitForFunction(() => {
        const hasCards = document.querySelectorAll('.card p.font-bold.text-sm.text-slate-900').length > 0;
        const bodyText = document.body?.innerText || '';
        const hasNotice = bodyText.includes('Benchmark comparison failed') || bodyText.includes('Benchmark comparison is syncing:');
        return hasCards || hasNotice;
      }, undefined, { timeout: 120000 });
      const strategyCards = page.locator('.card p.font-bold.text-sm.text-slate-900');
      const compareCardCount = await strategyCards.count();
      if (compareCardCount > 0) {
        result.compare.green = true;
        result.compare.reason = `Loaded ${compareCardCount} strategy cards`;
      } else {
        result.compare.green = false;
        result.compare.reason = 'Header visible but no strategy cards found';
      }
    } catch (error) {
      result.compare.green = false;
      result.compare.reason = String(error?.message || error);
    }
    await shot(page, 'quick-04-compare');

    try {
      await page.getByRole('button', { name: 'AI Strategy Assistant' }).click();
      await page.getByPlaceholder('Ask about stocks, taxes, strategy...').fill('Give me a 2-line summary of this portfolio risk and one action item.');
      await page.locator('.chat-window button.btn-primary').click();
      await page.waitForFunction(() => {
        const bubbles = Array.from(document.querySelectorAll('.chat-window .bg-slate-100.rounded-2xl'));
        return bubbles.some((el) => {
          const t = (el.textContent || '').trim();
          return t.length > 10 && !t.includes("Hi! I'm your NSE Atlas Portfolio Assistant");
        });
      }, undefined, { timeout: 120000 });
      result.aiChat.green = true;
      result.aiChat.reason = 'Received non-greeting assistant reply';
    } catch (error) {
      result.aiChat.green = false;
      result.aiChat.reason = String(error?.message || error);
    }
    await shot(page, 'quick-05-ai-chat');

    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    await shot(page, 'quick-00-failure');
    result.error = String(error?.stack || error);
    console.log(JSON.stringify(result, null, 2));
    process.exit(1);
  } finally {
    await browser.close();
  }
}

run();
