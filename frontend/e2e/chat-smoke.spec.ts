import { test, expect } from '@playwright/test';

/**
 * E2E smoke for Phase 4. Requires the FastAPI backend running on http://localhost:8000.
 * To run locally: in one terminal `cd backend && uvicorn api.main:app --port 8000`,
 * then in another `cd frontend && npx playwright test`.
 *
 * If the backend is unreachable the test will fail at the SSE step — that failure
 * mode is intentional (we want the smoke to catch backend regressions too).
 */

test.describe('Phase 4 chat smoke', () => {
  test('home page renders the three columns and accepts an example prompt', async ({
    page,
  }) => {
    await page.goto('/');

    // Three column anchors visible on desktop viewport.
    await expect(
      page.getByRole('heading', { name: 'Conversations' }),
    ).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Reasoning trace' }),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Chat' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible();

    // Empty-state example prompts present.
    await expect(
      page.getByRole('button', {
        name: 'Surcharge for 15kg Bounce, Bangkok → Nonthaburi',
      }),
    ).toBeVisible();

    // Bangkok Metro phrasing audit — page MUST NOT contain "Central Region" anywhere.
    const bodyText = await page.locator('body').innerText();
    expect(bodyText).not.toContain('Central Region');
  });

  test('clicking the first example prompt streams a trace and renders the breakdown table', async ({
    page,
  }) => {
    await page.goto('/');
    await page
      .getByRole('button', {
        name: 'Surcharge for 15kg Bounce, Bangkok → Nonthaburi',
      })
      .click();

    // Within 30s the breakdown table should appear (Gemini API + tools take a few seconds).
    await expect(page.getByRole('table')).toBeVisible({ timeout: 30_000 });

    // Trace panel should have at least 4 trace step buttons (planner + fuel + route + pricing + response).
    const traceButtons = await page
      .locator('aside')
      .nth(1)
      .getByRole('button', { expanded: false })
      .all();
    expect(traceButtons.length).toBeGreaterThanOrEqual(4);
  });

  test('Dashboard tab renders both charts', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Dashboard' }).click();
    await expect(
      page.getByRole('heading', { name: 'Diesel price (THB/L)' }),
    ).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Recent surcharges' }),
    ).toBeVisible();
    // Range toggle visible.
    await expect(page.getByRole('radio', { name: '30d' })).toBeVisible();
  });
});
