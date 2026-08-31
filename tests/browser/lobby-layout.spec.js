import { expect, test } from "@playwright/test";

async function createLobby(page, botCount, { maxPlayers = 4, isPublic = false } = {}) {
  await page.goto("/");
  await page.locator("#nameInput").fill("A");
  await page.getByRole("button", { name: "Change name" }).click();
  await page.getByRole("button", { name: "Create Lobby", exact: true }).click();
  await page.getByRole("button", { name: String(maxPlayers), exact: true }).click();
  await page.getByRole("button", {
    name: isPublic ? "Public" : "Private",
    exact: true
  }).click();
  await expect(page.locator(".player-name-row")).toHaveCount(1);

  const addBot = page.getByRole("button", { name: "Add Bot" });
  for (let index = 0; index < botCount; index += 1) {
    await addBot.click();
    await expect(page.locator(".player-name-row")).toHaveCount(index + 2);
  }
}

async function joinConfiguredLobby(page, { hostName, code, isPublic, playerName }) {
  await page.goto("/");
  await page.locator("#nameInput").fill(playerName);
  await page.getByRole("button", { name: "Change name" }).click();
  await page.getByRole("button", { name: "Join Lobby" }).click();
  if (isPublic) {
    const row = page.locator(".available-lobby-row").filter({ hasText: `${hostName}'s lobby` });
    await expect(row).toBeVisible();
    await row.click();
    await row.getByRole("button", { name: `Join ${hostName}'s lobby` }).click();
  } else {
    await page.locator("#lobbyInput").fill(code);
    await page.getByRole("button", { name: "Join", exact: true }).click();
  }
  await expect(page.locator(".lobby-summary-name")).toHaveText(`${hostName}'s lobby`);
}

test("mobile game follows the visible viewport and keeps edge controls inside it", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true
  });
  const page = await context.newPage();
  await createLobby(page, 1, { maxPlayers: 2 });
  await page.getByRole("button", { name: "Start Game" }).click();
  await expect(page.locator("#playerHand img")).not.toHaveCount(0);

  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute("content", "#0b6b42");
  await expect(page.locator('meta[name="apple-mobile-web-app-capable"]'))
    .toHaveAttribute("content", "yes");
  await expect(page.locator('meta[name="apple-mobile-web-app-status-bar-style"]'))
    .toHaveAttribute("content", "black-translucent");

  const inspectLayout = () => page.evaluate(() => {
    const header = document.querySelector("header").getBoundingClientRect();
    const title = document.querySelector("h1").getBoundingClientRect();
    const currentCards = document.querySelector("#currentCards").getBoundingClientRect();
    const playerHand = document.querySelector("#playerHand").getBoundingClientRect();
    const turnText = document.querySelector("#turnText").getBoundingClientRect();
    const cardTops = [...document.querySelectorAll("#playerHand .card")]
      .map(card => card.getBoundingClientRect().top);
    return {
      viewportHeight: innerHeight,
      bodyHeight: document.body.getBoundingClientRect().height,
      htmlBackground: getComputedStyle(document.documentElement).backgroundColor,
      htmlBackgroundImage: getComputedStyle(document.documentElement).backgroundImage,
      bodyBackground: getComputedStyle(document.body).backgroundColor,
      headerTop: header.top,
      headerBottom: header.bottom,
      titleHeight: title.height,
      currentCardsBottom: currentCards.bottom,
      handTop: playerHand.top,
      handBottom: playerHand.bottom,
      turnTextBottom: turnText.bottom,
      firstCardTop: Math.min(...cardTops),
    };
  });

  for (const height of [844, 650]) {
    await page.setViewportSize({ width: 390, height });
    await page.waitForTimeout(100);
    const layout = await inspectLayout();
    expect(layout.viewportHeight).toBe(height);
    expect(layout.bodyHeight).toBeCloseTo(height, 0);
    expect(layout.htmlBackground).toBe("rgb(11, 107, 66)");
    expect(layout.htmlBackgroundImage).toContain("background.png");
    expect(layout.htmlBackgroundImage).toContain("linear-gradient");
    expect(layout.bodyBackground).toBe("rgba(0, 0, 0, 0)");
    expect(layout.headerTop).toBeGreaterThanOrEqual(0);
    expect(layout.headerBottom).toBeLessThanOrEqual(height);
    expect(layout.titleHeight).toBeLessThanOrEqual(28);
    expect(layout.currentCardsBottom).toBeLessThan(layout.handTop);
    expect(layout.firstCardTop - layout.handTop).toBeGreaterThanOrEqual(15);
    expect(layout.turnTextBottom).toBeLessThanOrEqual(layout.firstCardTop - 10);
    expect(layout.handBottom).toBeLessThanOrEqual(height);
    expect(layout.handBottom).toBeGreaterThanOrEqual(height - 2);
  }

  await context.close();
});

test("mobile game has a non-overlapping landscape layout", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 844, height: 390 },
    hasTouch: true,
    isMobile: true
  });
  const page = await context.newPage();
  await createLobby(page, 1, { maxPlayers: 2 });
  await page.getByRole("button", { name: "Start Game" }).click();
  await expect(page.locator("#playerHand img")).not.toHaveCount(0);

  const layout = await page.evaluate(() => {
    const box = selector => document.querySelector(selector).getBoundingClientRect();
    const opponentBoxes = [...document.querySelectorAll(".player-entry")]
      .filter(element => getComputedStyle(element).display !== "none")
      .map(element => element.getBoundingClientRect());
    const handCards = [...document.querySelectorAll("#playerHand .card")]
      .map(element => element.getBoundingClientRect());
    return {
      viewport: { width: innerWidth, height: innerHeight },
      scrollWidth: document.documentElement.scrollWidth,
      header: box("header"),
      current: box("#currentCards"),
      hand: box("#playerHand"),
      opponentsBottom: Math.max(...opponentBoxes.map(item => item.bottom)),
      firstCardTop: Math.min(...handCards.map(item => item.top)),
      lastCardBottom: Math.max(...handCards.map(item => item.bottom)),
    };
  });

  expect(layout.scrollWidth).toBeLessThanOrEqual(layout.viewport.width);
  expect(layout.header.top).toBeGreaterThanOrEqual(0);
  expect(layout.opponentsBottom).toBeLessThan(layout.current.top);
  expect(layout.current.bottom).toBeLessThan(layout.firstCardTop);
  expect(layout.lastCardBottom).toBeLessThanOrEqual(layout.viewport.height);
  expect(layout.hand.bottom).toBeLessThanOrEqual(layout.viewport.height);
  await context.close();
});

test("empty lobby browser uses stacked private search and compact refresh control", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true
  });
  const page = await context.newPage();
  await page.goto("/");
  await page.getByRole("button", { name: "Join Lobby" }).click();
  await expect(page.locator("#availableLobbiesEmpty")).toHaveText("No lobbies are available yet");

  const layout = await page.locator("#lobby-browser-widget .lobby-modal-content").evaluate(content => {
    const refresh = content.querySelector("#refreshLobbiesButton");
    const codeInput = content.querySelector("#lobbyInput");
    const join = content.querySelector("#joinLobbyButton");
    const nameInput = document.querySelector("#nameInput");
    const refreshBox = refresh.getBoundingClientRect();
    const codeBox = codeInput.getBoundingClientRect();
    const joinBox = join.getBoundingClientRect();
    const nameBox = nameInput.getBoundingClientRect();
    return {
      emptyAlign: getComputedStyle(content.querySelector("#availableLobbiesEmpty")).textAlign,
      refreshText: refresh.textContent.trim(),
      refreshIconSize: getComputedStyle(refresh).fontSize,
      refreshWeight: getComputedStyle(refresh).fontWeight,
      refreshWidth: refreshBox.width,
      refreshHeight: refreshBox.height,
      refreshRadius: getComputedStyle(refresh).borderRadius,
      refreshBelowInput: refreshBox.top > codeBox.bottom,
      joinOnInputLine: Math.abs((joinBox.top + joinBox.bottom) / 2 - (codeBox.top + codeBox.bottom) / 2) < 2,
      inputJoinGap: joinBox.left - codeBox.right,
      codeWidth: codeBox.width,
      nameWidth: nameBox.width,
    };
  });
  expect(layout.emptyAlign).toBe("left");
  expect(layout.refreshText).toBe("Refresh");
  expect(layout.refreshIconSize).toBe("12px");
  expect(layout.refreshWeight).toBe("400");
  expect(layout.refreshWidth).toBe(68);
  expect(layout.refreshHeight).toBe(22);
  expect(layout.refreshRadius).toBe("20px");
  expect(layout.refreshBelowInput).toBe(true);
  expect(layout.joinOnInputLine).toBe(true);
  expect(layout.inputJoinGap).toBeCloseTo(5, 0);
  expect(layout.codeWidth).toBeLessThan(layout.nameWidth * 1.2);
  const mobileInput = page.locator("#lobbyInput");
  const mobileJoin = page.locator("#joinLobbyButton");
  const mobileInputWidth = await mobileInput.evaluate(element => element.getBoundingClientRect().width);
  const mobileJoinLeft = await mobileJoin.evaluate(element => element.getBoundingClientRect().left);
  await mobileInput.tap();
  await page.waitForTimeout(250);
  const mobileFocus = await mobileInput.evaluate(element => {
    const style = getComputedStyle(element);
    return {
      width: element.getBoundingClientRect().width,
      outline: style.outlineStyle,
      shadow: style.boxShadow
    };
  });
  expect(mobileFocus.width).toBeGreaterThan(mobileInputWidth);
  expect(mobileFocus.outline).toBe("none");
  expect(mobileFocus.shadow).toContain("255, 165, 0");
  expect(await mobileJoin.evaluate(element => element.getBoundingClientRect().left)).toBe(mobileJoinLeft);
  const refresh = page.locator("#refreshLobbiesButton");
  await refresh.tap();
  await page.waitForTimeout(20);
  await expect(refresh).not.toBeFocused();
  const refreshShadow = await refresh.evaluate(button => getComputedStyle(button).boxShadow);
  expect(refreshShadow).not.toContain("255, 165, 0");
  await context.close();
});

test("the rules dialog keeps its desktop size and closes on mobile", async ({ browser }) => {
  const desktopContext = await browser.newContext({ viewport: { width: 1200, height: 900 } });
  const desktop = await desktopContext.newPage();
  await desktop.goto("/");

  await desktop.getByRole("button", { name: "Rules" }).click();
  await expect(desktop.locator("#rules-widget")).toBeVisible();
  const desktopRulesWidth = await desktop.locator(".rules-widget-content").evaluate(element =>
    element.getBoundingClientRect().width
  );
  expect(desktopRulesWidth).toBe(720);
  await desktopContext.close();

  const mobileContext = await browser.newContext({
    viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true
  });
  const mobile = await mobileContext.newPage();
  await mobile.goto("/");
  await mobile.getByRole("button", { name: "Rules" }).tap();
  await expect(mobile.locator("#rules-widget")).toBeVisible();
  await mobile.getByRole("button", { name: "Close rules" }).tap();
  await expect(mobile.locator("#rules-widget")).toBeHidden();
  await mobileContext.close();
});

for (const device of ["desktop", "mobile"]) {
  test(`the create-lobby close control is fully clickable on ${device}`, async ({ browser }) => {
    const isMobile = device === "mobile";
    const context = await browser.newContext({
      viewport: isMobile ? { width: 390, height: 844 } : { width: 1200, height: 800 },
      hasTouch: isMobile,
      isMobile,
    });
    const page = await context.newPage();
    await page.goto("/");

    for (const point of ["top-left", "top-right", "center", "bottom-left", "bottom-right"]) {
      const createButton = page.getByRole("button", { name: "Create Lobby", exact: true });
      if (isMobile) await createButton.tap();
      else await createButton.click();

      const closeBox = await page.getByRole("button", { name: "Close create lobby dialog" }).boundingBox();
      const x = point.endsWith("left")
        ? closeBox.x + 2
        : point.endsWith("right")
          ? closeBox.x + closeBox.width - 2
          : closeBox.x + closeBox.width / 2;
      const y = point.startsWith("top")
        ? closeBox.y + 2
        : point.startsWith("bottom")
          ? closeBox.y + closeBox.height - 2
          : closeBox.y + closeBox.height / 2;

      if (isMobile) await page.touchscreen.tap(x, y);
      else await page.mouse.click(x, y);
      await expect(page.locator("#create-lobby-widget")).toBeHidden();
    }

    await context.close();
  });
}

test("desktop private code field grows in place and releases focus after Join", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1200, height: 800 } });
  const page = await context.newPage();
  await page.goto("/");
  const homeLayout = await page.locator("#homeLobbyActions").evaluate(actions => {
    const create = actions.querySelector("#createLobbyButton").getBoundingClientRect();
    const join = actions.querySelector("#joinPublicLobbyButton").getBoundingClientRect();
    const quick = actions.querySelector("#quickPlayButton").getBoundingClientRect();
    return {
      firstRow: Math.abs(create.top - join.top) < 2,
      createBeforeJoin: create.left < join.left,
      quickBelow: quick.top > create.bottom,
      quickCentered: Math.abs((quick.left + quick.right) / 2 - innerWidth / 2) < 2
    };
  });
  expect(homeLayout).toEqual({
    firstRow: true,
    createBeforeJoin: true,
    quickBelow: true,
    quickCentered: true
  });
  await page.getByRole("button", { name: "Join Lobby" }).click();
  const input = page.locator("#lobbyInput");
  const join = page.locator("#joinLobbyButton");
  const controlHeights = await page.locator(".private-code-join").evaluate(container => ({
    input: container.querySelector("#lobbyInput").getBoundingClientRect().height,
    join: container.querySelector("#joinLobbyButton").getBoundingClientRect().height,
  }));
  expect(controlHeights.join).toBe(controlHeights.input);
  expect(controlHeights.join).toBe(26);
  const before = await input.evaluate(element => element.getBoundingClientRect().toJSON());
  const joinLeftBefore = await join.evaluate(element => element.getBoundingClientRect().left);
  await page.mouse.click(before.x + before.width / 2, before.y + 2);
  await expect(input).toBeFocused();
  await page.keyboard.type("zzzzzz");
  await expect(join).toBeEnabled();
  await page.waitForTimeout(250);
  const focused = await input.evaluate(element => {
    const box = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      left: box.left,
      width: box.width,
      outline: style.outlineStyle,
      shadow: style.boxShadow
    };
  });
  expect(focused.width).toBeGreaterThan(before.width);
  expect(focused.outline).toBe("none");
  expect(focused.shadow).toContain("255, 165, 0");
  expect(await join.evaluate(element => element.getBoundingClientRect().left)).toBe(joinLeftBefore);

  await input.fill("deadbe");
  await page.getByRole("button", { name: "Join", exact: true }).click();
  await expect(input).not.toBeFocused();
  await expect(page.locator("#lobbyBrowserError")).toHaveText("The private lobby was not found");
  const inputAfterError = await input.boundingBox();
  await page.mouse.click(inputAfterError.x + inputAfterError.width / 2, inputAfterError.y + 2);
  await expect(input).toBeFocused();
  await page.keyboard.type("zzzzzz");
  await expect(join).toBeEnabled();
  const activeJoinBox = await join.boundingBox();
  await page.mouse.click(
    activeJoinBox.x + activeJoinBox.width / 2,
    activeJoinBox.y + activeJoinBox.height - 2
  );
  await expect(input).not.toBeFocused();
  await expect(page.locator("#lobbyBrowserError")).toHaveText("The private lobby was not found");
  const close = page.locator("#closeLobbyBrowserWidget");
  const closeBox = await close.boundingBox();
  await page.mouse.click(closeBox.x + closeBox.width / 2, closeBox.y + closeBox.height - 2);
  await expect(page.locator("#lobby-browser-widget")).toBeHidden();
  await context.close();
});

for (const lobbyType of ["Public", "Private"]) {
  test(`${lobbyType} accepts clicks across the full visible create-lobby button`, async ({ browser }) => {
    for (const viewport of [{ width: 1200, height: 800 }, { width: 700, height: 450 }]) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      await page.goto("/");
      await page.getByRole("button", { name: "Create Lobby", exact: true }).click();
      const button = page.getByRole("button", { name: lobbyType, exact: true });
      const hitTargets = await button.evaluate(element => {
        const box = element.getBoundingClientRect();
        return [[0.5, 0.03], [0.5, 0.97], [0.03, 0.5], [0.97, 0.5], [0.5, 0.5]].map(([x, y]) => {
          const target = document.elementFromPoint(box.left + box.width * x, box.top + box.height * y);
          return target?.id;
        });
      });
      expect(hitTargets.every(id => id === `create${lobbyType}LobbyButton`)).toBe(true);
      const box = await button.boundingBox();
      await page.mouse.click(box.x + box.width - 2, box.y + box.height / 2);
      await expect(page.locator("#create-lobby-widget")).toBeHidden();
      await expect(page.locator(".lobby-summary-name")).toBeVisible();
      await context.close();
    }
  });

  test(`${lobbyType} accepts taps across the full visible create-lobby button on mobile`, async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true
    });
    const page = await context.newPage();
    await page.goto("/");
    await page.getByRole("button", { name: "Create Lobby", exact: true }).tap();
    const button = page.getByRole("button", { name: lobbyType, exact: true });
    const box = await button.boundingBox();
    await page.touchscreen.tap(box.x + box.width - 2, box.y + box.height / 2);
    await expect(page.locator("#create-lobby-widget")).toBeHidden();
    await expect(page.locator(".lobby-summary-name")).toBeVisible();
    await context.close();
  });
}

test("mobile private code and Join accept taps across their full visible areas", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true
  });
  const page = await context.newPage();
  await page.goto("/");
  await page.getByRole("button", { name: "Join Lobby", exact: true }).tap();

  const input = page.locator("#lobbyInput");
  const inputBox = await input.boundingBox();
  await page.touchscreen.tap(inputBox.x + inputBox.width / 2, inputBox.y + 2);
  await expect(input).toBeFocused();
  await page.keyboard.type("deadbe");

  const join = page.getByRole("button", { name: "Join", exact: true });
  await expect(join).toBeEnabled();
  const joinBox = await join.boundingBox();
  await page.touchscreen.tap(joinBox.x + joinBox.width / 2, joinBox.y + joinBox.height - 2);
  await expect(page.locator("#lobbyBrowserError")).toHaveText("The private lobby was not found");

  const inputAfterError = await input.boundingBox();
  await page.touchscreen.tap(
    inputAfterError.x + inputAfterError.width / 2,
    inputAfterError.y + inputAfterError.height - 2
  );
  await expect(input).toBeFocused();
  await context.close();
});

test("lobby rows share the longest width and align kick controls", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1200, height: 800 } });
  const page = await context.newPage();
  await createLobby(page, 3);
  expect(await page.locator(".buttonContainer").evaluate(element => getComputedStyle(element).gap)).toBe("12px");
  await expect(page.locator(".host-label")).toHaveCount(1);
  await expect(page.locator(".host-label")).toHaveText("HOST");

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
  expect(rows.every(row => row.nameLeft - row.rowLeft <= 1.5)).toBe(true);

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
  const homeLayout = await page.locator("#homeLobbyActions").evaluate(actions => {
    const create = actions.querySelector("#createLobbyButton").getBoundingClientRect();
    const join = actions.querySelector("#joinPublicLobbyButton").getBoundingClientRect();
    const quick = actions.querySelector("#quickPlayButton").getBoundingClientRect();
    const error = document.querySelector(".errorMessage").getBoundingClientRect();
    return {
      firstRow: Math.abs(create.top - join.top) < 2,
      createBeforeJoin: create.left < join.left,
      quickBelow: quick.top > create.bottom,
      quickCentered: Math.abs((quick.left + quick.right) / 2 - innerWidth / 2) < 2,
      errorHeight: error.height
    };
  });
  expect(homeLayout.firstRow).toBe(true);
  expect(homeLayout.createBeforeJoin).toBe(true);
  expect(homeLayout.quickBelow).toBe(true);
  expect(homeLayout.quickCentered).toBe(true);
  expect(homeLayout.errorHeight).toBeGreaterThanOrEqual(52);
  await page.locator("#nameInput").fill("A");
  await page.getByRole("button", { name: "Change name" }).tap();
  await page.getByRole("button", { name: "Create Lobby", exact: true }).tap();
  const dialog = page.getByRole("dialog", { name: "Create Lobby" });
  await expect(dialog).toBeVisible();
  const mobileOptions = await dialog.locator(".lobby-type-option").evaluateAll(options =>
    options.map(option => {
      const button = option.querySelector("button").getBoundingClientRect();
      const text = option.querySelector("p").getBoundingClientRect();
      return { buttonTop: button.top, buttonBottom: button.bottom, textTop: text.top };
    })
  );
  expect(mobileOptions[0].buttonTop).toBeCloseTo(mobileOptions[1].buttonTop, 1);
  expect(mobileOptions.every(option => option.textTop > option.buttonBottom)).toBe(true);
  await page.getByRole("button", { name: "4", exact: true }).tap();
  await page.getByRole("button", { name: "Private", exact: true }).tap();
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

test("player name backgrounds are limited to the lobby", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await createLobby(page, 1, { maxPlayers: 2 });
  const lobbyBackground = await page.locator(".player-name-row").first().evaluate(element =>
    getComputedStyle(element).backgroundColor
  );
  expect(lobbyBackground).not.toBe("rgba(0, 0, 0, 0)");

  await page.getByRole("button", { name: "Start Game" }).click();
  await expect(page.locator("#currentCards")).toBeVisible();
  const gameRows = await page.locator(".player-name-row").evaluateAll(rows =>
    rows.map(row => ({
      background: getComputedStyle(row).backgroundColor,
      border: getComputedStyle(row).borderTopWidth
    }))
  );
  expect(gameRows.every(row => row.background === "rgba(0, 0, 0, 0)")).toBe(true);
  expect(gameRows.every(row => row.border === "0px")).toBe(true);
  await context.close();
});

test("refreshing an active game asks before reconnecting", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await createLobby(page, 1, { maxPlayers: 2 });
  await page.getByRole("button", { name: "Start Game" }).click();
  await expect(page.locator("#playerHand img")).not.toHaveCount(0);

  await page.reload();
  await expect(page.getByRole("dialog", { name: "Game disconnected" })).toBeVisible();
  await expect(page.locator("#homeLobbyActions")).toBeVisible();
  const seconds = Number(await page.locator("#reconnectGameTimer").textContent());
  expect(seconds).toBeGreaterThan(0);
  expect(seconds).toBeLessThanOrEqual(60);

  await page.getByRole("button", { name: "Reconnect Game" }).click();
  await expect(page.locator("#playerHand img")).not.toHaveCount(0, { timeout: 10_000 });
  await expect(page.locator("#currentCards")).toBeVisible();
  await expect(page.locator("#rightCard img")).toHaveCount(1);
  await expect(page.locator("#cardsLeft")).not.toHaveText("");
  await expect(page.locator(".opponent_hand")).toHaveCount(2);
  await expect(page.locator("#usersHeader")).toBeVisible();
  await expect(page.locator(".player-entry:visible")).toHaveCount(1);
  await expect(page.locator(".opponent_hand:visible")).toHaveCount(1);
  await expect(page.locator(".opponentScores:visible")).toHaveCount(1);
  await expect(page.locator("#welcomeMessage")).toBeHidden();
  await expect(page.locator("#homeLobbyActions")).toBeHidden();
  await expect(page.locator("#nameForm")).toBeHidden();
  await context.close();
});

test("mobile game waits in the background and reconnects silently on return", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true
  });
  await context.addInitScript(() => {
    globalThis.__BACKYARD_BRIDGE_TEST__ = true;
  });
  const page = await context.newPage();
  await createLobby(page, 1, { maxPlayers: 2 });
  await page.getByRole("button", { name: "Start Game" }).click();
  await expect(page.locator("#playerHand img")).not.toHaveCount(0);

  await page.evaluate(() => {
    globalThis.__forcedVisibilityState = "hidden";
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => globalThis.__forcedVisibilityState
    });
    globalThis.__backyardBridge.getState().ws.close();
  });
  await expect.poll(() => page.evaluate(() => {
    const state = globalThis.__backyardBridge.getState();
    return { requested: state.reconnectRequested, readyState: state.ws.readyState };
  })).toEqual({ requested: false, readyState: 3 });
  await expect(page.getByRole("dialog", { name: "Game disconnected" })).toBeHidden();

  await page.evaluate(() => {
    globalThis.__forcedVisibilityState = "visible";
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect.poll(() => page.evaluate(() => {
    const state = globalThis.__backyardBridge.getState();
    return {
      reconnecting: state.reconnecting,
      requested: state.reconnectRequested,
      readyState: state.ws.readyState
    };
  }), { timeout: 10_000 }).toEqual({
    reconnecting: false,
    requested: false,
    readyState: 1
  });
  await expect(page.locator("#currentCards")).toBeVisible();
  await expect(page.locator("#homeLobbyActions")).toBeHidden();
  await expect(page.locator("#usersHeader")).toBeVisible();
  await expect(page.locator(".player-entry:visible")).toHaveCount(1);
  await expect(page.locator(".opponent_hand:visible")).toHaveCount(1);
  await expect(page.locator(".opponentScores:visible")).toHaveCount(1);
  await page.evaluate(() => {
    const socket = globalThis.__backyardBridge.getState().ws;
    const send = socket.send.bind(socket);
    globalThis.__messagesAfterReconnect = [];
    socket.send = payload => {
      globalThis.__messagesAfterReconnect.push(JSON.parse(payload));
      send(payload);
    };
  });
  const pendingJackSuit = page.locator(
    '#jack-widget [role="button"][aria-disabled="false"]'
  ).first();
  if (await pendingJackSuit.isVisible()) {
    await pendingJackSuit.click();
  } else {
    const resumedAction = page.locator(
      '#leftCard[aria-disabled="false"], #rightCard[aria-disabled="false"]'
    ).first();
    await expect(resumedAction).toBeVisible({ timeout: 10_000 });
    await resumedAction.click();
  }
  await expect.poll(() => page.evaluate(() => globalThis.__messagesAfterReconnect))
    .toContainEqual(expect.objectContaining({ type: expect.stringMatching(/^(pc|dc|st)$/) }));
  await context.close();
});

test("another tab cannot inherit a game session from this tab", async ({ browser }) => {
  const context = await browser.newContext();
  const gamePage = await context.newPage();
  await createLobby(gamePage, 1, { maxPlayers: 2 });
  await gamePage.getByRole("button", { name: "Start Game" }).click();
  await expect(gamePage.locator("#playerHand img")).not.toHaveCount(0);

  const independentTab = await context.newPage();
  await independentTab.goto("/");
  await independentTab.reload();
  await expect(independentTab.locator("#homeLobbyActions")).toBeVisible();
  await expect(independentTab.getByRole("dialog", { name: "Game disconnected" })).toBeHidden();
  await expect(independentTab.locator("#currentCards")).toBeHidden();
  await context.close();
});

test("host Leave Game ends the active game for every participant", async ({ browser }) => {
  const hostContext = await browser.newContext();
  const guestContext = await browser.newContext();
  const host = await hostContext.newPage();
  const guest = await guestContext.newPage();
  await createLobby(host, 0, { maxPlayers: 2, isPublic: true });
  await guest.goto("/");
  await guest.getByRole("button", { name: "Join Lobby" }).click();
  const row = guest.locator(".available-lobby-row");
  await row.click();
  await row.getByRole("button", { name: "Join A's lobby" }).click();
  await host.getByRole("button", { name: "Start Game" }).click();
  await expect(host.locator("#playerHand img")).not.toHaveCount(0);
  await expect(guest.locator("#playerHand img")).not.toHaveCount(0);

  await host.locator("#leaveActiveGameButton").click();
  const confirmation = host.getByRole("dialog", { name: "Are you sure?" });
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button", { name: "Continue" }).click();
  await expect(confirmation).toBeHidden();
  await expect(host.locator("#playerHand img")).not.toHaveCount(0);
  await host.locator("#leaveActiveGameButton").click();
  await confirmation.getByRole("button", { name: "Leave", exact: true }).click();
  await expect(host.locator("#homeLobbyActions")).toBeVisible();
  await expect(guest.locator("#homeLobbyActions")).toBeVisible();
  await expect(guest.locator("#errorMessage")).toContainText("The host left the game");
  await guestContext.close();
  await hostContext.close();
});

test("refreshing the host lobby immediately closes it for every participant", async ({ browser }) => {
  const hostContext = await browser.newContext();
  const guestContext = await browser.newContext();
  const observerContext = await browser.newContext();
  const host = await hostContext.newPage();
  const guest = await guestContext.newPage();
  const observer = await observerContext.newPage();

  await createLobby(host, 0, { maxPlayers: 3, isPublic: true });
  await guest.goto("/");
  await guest.getByRole("button", { name: "Join Lobby" }).click();
  const row = guest.locator(".available-lobby-row");
  await row.click();
  await row.getByRole("button", { name: "Join A's lobby" }).click();
  await expect(host.locator(".player-name-row")).toHaveCount(2);

  await host.reload();
  await expect(host.locator("#homeLobbyActions")).toBeVisible();
  await expect(guest.locator("#homeLobbyActions")).toBeVisible();
  await expect(guest.locator("#errorMessage")).toContainText("The host left the lobby");
  await observer.goto("/");
  await observer.getByRole("button", { name: "Join Lobby" }).click();
  await expect(observer.locator("#availableLobbiesEmpty")).toBeVisible();
  await expect(observer.locator(".available-lobby-row")).toHaveCount(0);

  await observerContext.close();
  await guestContext.close();
  await hostContext.close();
});

test("public lobby is discoverable and joins at the configured capacity", async ({ browser }) => {
  const hostContext = await browser.newContext({ viewport: { width: 1200, height: 800 } });
  const guestContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const host = await hostContext.newPage();
  const guest = await guestContext.newPage();

  await host.goto("/");
  await host.locator("#nameInput").fill("Alice");
  await host.getByRole("button", { name: "Change name" }).click();
  await host.getByRole("button", { name: "Create Lobby", exact: true }).click();
  await host.getByRole("button", { name: "2", exact: true }).click();
  await host.getByRole("button", { name: "Public", exact: true }).click();
  await expect(host.locator(".lobby-summary-name")).toHaveText("Alice's lobby");
  await expect(host.locator(".lobby-summary-meta")).toContainText("Public lobby · 1/2 players");
  await expect(host.locator(".lobby-code-button")).toHaveCount(0);

  await guest.goto("/");
  await guest.getByRole("button", { name: "Join Lobby" }).click();
  await expect(guest.locator(".available-lobby-row")).toContainText("Alice's lobby");
  await expect(guest.locator(".available-lobby-row")).toContainText("1/2");
  await guest.locator(".available-lobby-row").click();
  const browserGeometry = await guest.locator("#lobby-browser-widget").evaluate(widget => {
    const content = widget.querySelector(".lobby-modal-content").getBoundingClientRect();
    const close = widget.querySelector("#closeLobbyBrowserWidget").getBoundingClientRect();
    const row = widget.querySelector(".available-lobby-row");
    const name = row.querySelector(".available-lobby-name").getBoundingClientRect();
    const capacity = row.querySelector(".available-lobby-capacity").getBoundingClientRect();
    const closeStyle = getComputedStyle(widget.querySelector("#closeLobbyBrowserWidget"));
    return {
      closeTop: close.top - content.top,
      closeRight: content.right - close.right,
      closeColor: closeStyle.color,
      closeShadow: closeStyle.boxShadow,
      aligned: Math.abs(name.top - capacity.top) < 2,
      boldText: row.querySelector("strong").textContent,
      fullNameBold: row.querySelector("strong").textContent === row.querySelector(".available-lobby-name").textContent
    };
  });
  expect(browserGeometry.closeTop).toBeCloseTo(0, 1);
  expect(browserGeometry.closeRight).toBeCloseTo(0, 1);
  expect(browserGeometry.closeColor).toBe("rgb(255, 255, 255)");
  expect(browserGeometry.closeShadow).not.toBe("none");
  expect(browserGeometry.aligned).toBe(true);
  expect(browserGeometry.boldText).toBe("Alice");
  expect(browserGeometry.fullNameBold).toBe(false);
  await guest.getByRole("button", { name: "Join Alice's lobby" }).click();

  await expect(guest.locator(".lobby-summary-name")).toHaveText("Alice's lobby");
  await expect(host.locator(".player-name-row")).toHaveCount(2);
  await expect(host.getByRole("button", { name: "Start Game" })).toBeEnabled();
  expect(await guest.evaluate(() => document.body.scrollWidth > innerWidth)).toBe(false);

  await guestContext.close();
  await hostContext.close();
});

test("open lobby list updates capacity automatically", async ({ browser }) => {
  const hostContext = await browser.newContext();
  const guestContext = await browser.newContext();
  const host = await hostContext.newPage();
  const guest = await guestContext.newPage();
  await createLobby(host, 0, { maxPlayers: 4, isPublic: true });
  await guest.goto("/");
  await guest.getByRole("button", { name: "Join Lobby" }).click();
  const row = guest.locator(".available-lobby-row").filter({ hasText: "A's lobby" });
  await expect(row.locator(".available-lobby-capacity")).toHaveText("1/4");

  await host.getByRole("button", { name: "Add Bot" }).click();
  await expect(host.locator(".lobby-summary-meta")).toContainText("2/4 players");
  await expect(row.locator(".available-lobby-capacity")).toHaveText("2/4", { timeout: 5500 });
  await guestContext.close();
  await hostContext.close();
});

test("private lobby is listed with a lock and joins only after entering its code", async ({ browser }) => {
  const hostContext = await browser.newContext({ viewport: { width: 1200, height: 800 } });
  const guestContext = await browser.newContext({
    viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true
  });
  const host = await hostContext.newPage();
  const guest = await guestContext.newPage();
  await createLobby(host, 0, { maxPlayers: 2 });
  const codeText = await host.locator(".lobby-code-button").textContent();
  const code = codeText.match(/[0-9a-f]{6}/)[0];

  await guest.goto("/");
  await guest.getByRole("button", { name: "Join Lobby" }).click();
  const row = guest.locator(".available-lobby-row").filter({ hasText: "A's lobby" });
  await expect(row.getByRole("img", { name: "Private lobby" })).toBeVisible();
  await row.click();
  await row.getByRole("button", { name: "Join A's lobby" }).click();
  await expect(guest.locator("#lobbyInput")).toBeFocused();
  await guest.locator("#lobbyInput").fill("deadbe");
  await guest.getByRole("button", { name: "Join", exact: true }).click();
  await expect(guest.locator("#lobbyInput")).toHaveValue("");
  await expect(guest.locator("#lobbyBrowserError")).toContainText("not found");
  await guest.waitForTimeout(20);
  const privateFocus = await guest.locator("#lobby-browser-widget").evaluate(widget => {
    const input = widget.querySelector("#lobbyInput");
    const join = widget.querySelector("#joinLobbyButton");
    return {
      inputFocused: document.activeElement === input,
      joinFocused: document.activeElement === join,
      inputShadow: getComputedStyle(input).boxShadow,
      joinShadow: getComputedStyle(join).boxShadow
    };
  });
  expect(privateFocus.inputFocused).toBe(false);
  expect(privateFocus.joinFocused).toBe(false);
  expect(privateFocus.inputShadow).not.toContain("255, 165, 0");
  expect(privateFocus.joinShadow).not.toContain("255, 165, 0");
  await expect(guest.locator("#lobbyBrowserError")).toHaveText("", { timeout: 3500 });
  await guest.locator("#lobbyInput").fill(code);
  await guest.getByRole("button", { name: "Join", exact: true }).click();
  await expect(guest.locator(".lobby-summary-name")).toHaveText("A's lobby");
  expect(await guest.evaluate(() => document.body.scrollWidth > innerWidth)).toBe(false);
  await guestContext.close();
  await hostContext.close();
});

test("Quick Play ignores a full public lobby", async ({ browser }) => {
  const fullContext = await browser.newContext();
  const openContext = await browser.newContext();
  const guestContext = await browser.newContext();
  const full = await fullContext.newPage();
  const open = await openContext.newPage();
  const guest = await guestContext.newPage();
  await createLobby(full, 1, { maxPlayers: 2, isPublic: true });
  await createLobby(open, 0, { maxPlayers: 3, isPublic: true });

  await guest.goto("/");
  await guest.getByRole("button", { name: "Quick Play" }).click();
  await expect(guest.locator(".lobby-summary-name")).toHaveText("A's lobby");
  await expect(open.locator(".player-name-row")).toHaveCount(2);
  await expect(full.locator(".player-name-row")).toHaveCount(2);
  await guestContext.close();
  await openContext.close();
  await fullContext.close();
});

for (const isPublic of [true, false]) {
  for (const playerCount of [2, 3, 4]) {
    test(`${isPublic ? "public" : "private"} ${playerCount}-player session works with active clients`, async ({ browser }) => {
      test.setTimeout(45_000);
      const contexts = [];
      try {
        const hostContext = await browser.newContext({ viewport: { width: 1200, height: 800 } });
        contexts.push(hostContext);
        const host = await hostContext.newPage();
        const hostName = `H${playerCount}${isPublic ? "Pub" : "Priv"}`;
        await host.goto("/");
        await host.locator("#nameInput").fill(hostName);
        await host.getByRole("button", { name: "Change name" }).click();
        await host.getByRole("button", { name: "Create Lobby", exact: true }).click();
        await host.getByRole("button", { name: String(playerCount), exact: true }).click();
        await host.getByRole("button", {
          name: isPublic ? "Public" : "Private", exact: true
        }).click();

        await expect(host.getByRole("button", { name: "Start Game" })).toBeDisabled();
        await expect(host.getByRole("button", { name: "Add Bot" })).toBeEnabled();
        await expect(host.getByRole("button", { name: "Leave Lobby" })).toBeVisible();
        const codeText = isPublic ? "" : await host.locator(".lobby-code-button").textContent();
        const code = isPublic ? "" : codeText.match(/[0-9a-f]{6}/)[0];
        const participants = [host];

        for (let index = 1; index < playerCount; index += 1) {
          const context = await browser.newContext({
            viewport: index % 2 ? { width: 390, height: 844 } : { width: 1200, height: 800 },
            hasTouch: index % 2 === 1,
            isMobile: index % 2 === 1
          });
          contexts.push(context);
          const participant = await context.newPage();
          await joinConfiguredLobby(participant, {
            hostName, code, isPublic, playerName: `P${playerCount}${index}`
          });
          participants.push(participant);
          await expect(host.locator(".player-name-row")).toHaveCount(index + 1);
          await expect(host.locator(".lobby-summary-meta")).toContainText(
            `${index + 1}/${playerCount} players`
          );
        }

        await expect(host.getByRole("button", { name: "Start Game" })).toBeEnabled();
        await expect(host.getByRole("button", { name: "Add Bot" })).toBeDisabled();
        await expect(host.locator(".kick-player-button")).toHaveCount(playerCount - 1);

        const kicked = participants.at(-1);
        await host.locator(".kick-player-button").last().click();
        await expect(kicked.locator("#homeLobbyActions")).toBeVisible();
        await expect(kicked.locator("#errorMessage")).toContainText("removed you from the lobby");
        await joinConfiguredLobby(kicked, {
          hostName, code, isPublic, playerName: `P${playerCount}${playerCount - 1}`
        });
        await expect(host.locator(".player-name-row")).toHaveCount(playerCount);

        await host.getByRole("button", { name: "Start Game" }).click();
        for (const participant of participants) {
          await expect(participant.locator("#playerHand img")).not.toHaveCount(0);
          await expect(participant.locator("#currentCards")).toBeVisible();
          await expect(participant.locator("#leaveActiveGameButton")).toBeVisible();
          await expect(participant.locator("#usersList > *")).toHaveCount(playerCount);
          await expect(participant.locator(".kick-player-button")).toHaveCount(0);
        }

        await host.getByRole("button", { name: "Rules" }).click();
        await expect(host.locator("#rules-widget")).toBeVisible();
        await host.locator("#closeRulesWidget").click();
        await expect(host.locator("#rules-widget")).toBeHidden();
        await host.locator("#leaveActiveGameButton").click();
        const confirmation = host.getByRole("dialog", { name: "Are you sure?" });
        await confirmation.getByRole("button", { name: "Continue" }).click();
        await expect(host.locator("#playerHand img")).not.toHaveCount(0);
        await host.locator("#leaveActiveGameButton").click();
        await confirmation.getByRole("button", { name: "Leave", exact: true }).click();
        for (const participant of participants) {
          await expect(participant.locator("#homeLobbyActions")).toBeVisible();
          await expect(participant.locator("#playerHand img")).toHaveCount(0);
        }
      } finally {
        await Promise.all(contexts.map(context => context.close()));
      }
    });
  }
}
