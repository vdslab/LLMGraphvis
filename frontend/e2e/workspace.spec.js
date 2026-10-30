import { test, expect } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dataset = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../sample_data/karate_club.graphml');

// Stop at the first unexpected browser failure and preserve its evidence.
test('register, upload, render, reconnect, tune and export', async ({ page }, testInfo) => {
  page.on('pageerror', error => { throw error; });
  page.on('console', message => {
    if (message.type() === 'error') throw new Error(message.text());
  });
  await page.goto('/register');
  await page.getByLabel('Username', { exact: true }).fill(`e2e-${Date.now()}-${testInfo.project.name}`);
  await page.getByLabel('Password', { exact: true }).fill('e2e-password-2026');
  await page.getByRole('button', { name: 'Create Account' }).click();
  await page.getByRole('link', { name: 'New Analysis' }).click();
  await expect(page.getByText('Choose a network to explore')).toBeVisible();
  await page.getByTestId('network-graph-panel').locator('input[type=file]').setInputFiles(dataset);
  const graph = page.getByTestId('network-graph');
  await expect(graph.locator('circle')).toHaveCount(34);
  const mobile = testInfo.project.name === 'mobile';
  if (mobile) await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await page.getByPlaceholder('Ask about this network…').fill('Show spring layout and parameter tuning');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(page.getByRole('tab', { name: 'Adjust', exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Chat', exact: true }).click();
  await expect(page.getByText('Regression ready.', { exact: false })).toBeVisible();
  await expect(page.locator('.katex')).toBeVisible();
  await page.getByRole('tab', { name: 'Adjust', exact: true }).click();
  const panel = page.getByRole('region', { name: 'Spring spacing' });
  await expect(panel).toBeVisible();
  await panel.getByRole('spinbutton').fill('0.8');
  const applied = page.waitForResponse(response => response.url().endsWith('/apply') && response.status() === 200);
  await panel.getByRole('button', { name: 'Apply', exact: true }).click();
  await applied;
  await page.reload(); // SSE and stored messages must recover together.
  if (mobile) await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await page.getByRole('tab', { name: 'Chat', exact: true }).click();
  await expect(page.getByText('Regression ready.', { exact: false })).toBeVisible();
  await page.getByRole('tab', { name: 'Adjust', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Spring spacing' }).getByRole('spinbutton')).toHaveValue('0.8');
  if (mobile) {
    await page.screenshot({ path: testInfo.outputPath('chat.png'), fullPage: true });
    await page.getByRole('button', { name: 'Network', exact: true }).click();
  }
  await expect(graph.locator('circle')).toHaveCount(34);
  await graph.getByRole('button', { name: 'Node 0', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Node Details' })).toBeVisible();
  await page.getByRole('button', { name: 'Close details' }).click();
  const before = await graph.locator('circle').first().evaluate(el => { window.savedCircle = el; return true; });
  expect(before).toBe(true);
  await page.getByRole('button', { name: /labels/i }).click();
  await expect.poll(() => graph.locator('circle').first().evaluate(el => el === window.savedCircle)).toBe(true);
  if (!mobile) {
    const separator = page.getByRole('separator', { name: 'Chat panel width' });
    const old = Number(await separator.getAttribute('aria-valuenow'));
    await separator.focus();
    await page.keyboard.press('ArrowLeft');
    await expect(separator).toHaveAttribute('aria-valuenow', String(old + 20));
  }
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: /export/i }).click();
  expect((await download).suggestedFilename()).toMatch(/\.graphml$/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('workspace.png'), fullPage: true });
});
