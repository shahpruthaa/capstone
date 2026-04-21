#!/usr/bin/env node

import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseUrl = 'http://localhost:3000';
const outDir = path.resolve('tmp', 'manual-smoke');

async function saveShot(page, name) {
  await fs.mkdir(outDir, { recursive: true });
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true });
}

async function testMarketEvents() {
  console.log('Testing Market Events tab...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  try {
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });

    // Navigate to EVENTS tab
    await page.getByRole('button', { name: 'EVENTS' }).click();
    await page.waitForTimeout(2000);

    // Check if the tab loaded
    const eventsTab = await page.locator('[data-testid="events-tab"]').isVisible().catch(() => false);
    console.log(`Events tab visible: ${eventsTab}`);

    // Check for market events content
    const marketEventsContent = await page.locator('.market-events-container').isVisible().catch(() => false);
    console.log(`Market events content visible: ${marketEventsContent}`);

    await saveShot(page, 'events-tab');

    console.log('Market Events test completed');
  } catch (error) {
    console.error('Market Events test failed:', error.message);
  } finally {
    await browser.close();
  }
}

async function testPortfolioRebalancing() {
  console.log('Testing Portfolio Rebalancing...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  try {
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });

    // Navigate to Portfolio tab
    await page.getByRole('button', { name: 'Portfolio' }).click();
    await page.getByRole('button', { name: 'Build Portfolio' }).click();

    // Generate a portfolio first
    await page.locator('input[type="number"]').first().fill('500000');
    await page.getByRole('button', { name: /Balanced/i }).click();
    await page.getByRole('button', { name: /Generate AI Portfolio/i }).click();

    // Wait for generation
    await page.waitForFunction(() => {
      const hasSuccess = document.querySelectorAll('.data-table tbody tr').length > 0;
      return hasSuccess;
    }, undefined, { timeout: 60000 });

    // Switch to Rebalance tab
    await page.getByRole('button', { name: 'Rebalance' }).click();
    await page.waitForTimeout(2000);

    // Check if rebalance content loaded
    const rebalanceContent = await page.locator('.rebalance-container').isVisible().catch(() => false);
    console.log(`Rebalance content visible: ${rebalanceContent}`);

    await saveShot(page, 'rebalance-tab');

    console.log('Portfolio Rebalancing test completed');
  } catch (error) {
    console.error('Portfolio Rebalancing test failed:', error.message);
  } finally {
    await browser.close();
  }
}

async function runTests() {
  console.log('Starting manual smoke tests for new GenAI features...\n');

  await testMarketEvents();
  console.log('');

  await testPortfolioRebalancing();
  console.log('');

  console.log('Manual smoke tests completed!');
  console.log(`Screenshots saved to: ${outDir}`);
}

runTests().catch((error) => {
  console.error('Test suite failed:', error);
  process.exit(1);
});