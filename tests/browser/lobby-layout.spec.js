import { expect, test } from "@playwright/test";

async function createLobby(page, botCount) {
  await page.goto("/");
  await page.locator("#nameInput").fill("A");
  await page.getByRole("button", { name: "Change name" }).click();
  await page.getByRole("button", { name: "New Game" }).click();
  await expect(page.locator(".player-name-row")).toHaveCount(1);

  const addBot = page.getByRole("button", { name: "Add Bot" });
  for (let index = 0; index < botCount; index += 1) {
    await addBot.click();
    await expect(page.locator(".player-name-row")).toHaveCount(index + 2);
  }
}

test("lobby rows share the longest width and align kick controls", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1200, height: 800 } });
  const page = await context.newPage();
  await createLobby(page, 3);

  const rows = await page.locator(".player-name-row").evaluateAll(elements =>
    elements.map(element => {
      const row = element.getBoundingClientRect();
      const name = element.querySelector("p").getBoundingClientRect();
      const kick = element.querySelector(".kick-player-button")?.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        rowWidth: row.width,
        rowHeight: row.height,
        rowLeft: row.left,
        rowRight: row.right,
        nameLeft: name.left,
        kickLeft: kick?.left ?? null,
        kickRight: kick?.right ?? null,
        kickHeight: kick?.height ?? null,
        background: style.backgroundColor,
        border: style.borderColor
      };
    })
  );

  expect(new Set(rows.map(row => row.rowWidth)).size).toBe(1);
  expect(new Set(rows.map(row => row.rowLeft)).size).toBe(1);
  expect(rows.every(row => row.nameLeft - row.rowLeft >= 7)).toBe(true);

  const removableRows = rows.filter(row => row.kickLeft !== null);
  expect(new Set(removableRows.map(row => row.kickLeft)).size).toBe(1);
  for (const row of removableRows) {
    expect(row.rowRight - row.kickRight).toBeCloseTo(1, 5);
    expect(row.rowHeight).toBe(20);
    expect(row.kickHeight).toBe(20);
  }

  expect(rows[0].background).toBe("rgba(216, 219, 226, 0.06)");
  expect(rows[0].border).toBe("rgba(216, 219, 226, 0.08)");
  await context.close();
});

test("mobile tap clears Add Bot focus and sticky highlighting", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true
  });
  const page = await context.newPage();
  await page.goto("/");
  await page.locator("#nameInput").fill("A");
  await page.getByRole("button", { name: "Change name" }).tap();
  await page.getByRole("button", { name: "New Game" }).tap();
  await expect(page.locator(".player-name-row")).toHaveCount(1);

  const addBot = page.getByRole("button", { name: "Add Bot" });
  await addBot.tap();
  await expect(page.locator(".player-name-row")).toHaveCount(2);
  await page.waitForTimeout(20);

  const state = await addBot.evaluate(button => ({
    focused: document.activeElement === button,
    boxShadow: getComputedStyle(button).boxShadow,
    outline: getComputedStyle(button).outlineStyle,
    coarsePointer: matchMedia("(pointer: coarse)").matches,
    noHover: matchMedia("(hover: none)").matches,
    overflows: document.body.scrollWidth > innerWidth
  }));

  expect(state.coarsePointer).toBe(true);
  expect(state.noHover).toBe(true);
  expect(state.focused).toBe(false);
  expect(state.outline).toBe("none");
  expect(state.boxShadow).not.toContain("255, 165, 0");
  expect(state.overflows).toBe(false);
  await context.close();
});
