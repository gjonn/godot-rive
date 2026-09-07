// Runs against the actual Web export, plus all artboards through its installed runtime.
// PLAYWRIGHT_MODULE may point to a locally installed playwright/index.mjs.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const url = process.env.WEB_URL || "http://127.0.0.1:8768/export/web/index.html";
const output = process.env.QA_OUTPUT || "/tmp/city-rive-web-qa";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1152, height: 648 } });
const errors = [];
page.on("pageerror", error => errors.push(String(error)));
page.on("console", message => {
  if (message.type() === "error") errors.push(message.text());
});
try {
  await page.goto(url);
  await page.waitForFunction(() => window.CityRive?.diagnostics().surfaces === 1, null, { timeout: 60000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${output}/menu.png` });
  await page.keyboard.press("Tab");
  await page.screenshot({ path: `${output}/menu_focus.png` });
  await page.mouse.click(576, 396);
  await page.waitForFunction(() => window.CityRive?.diagnostics().surfaces > 10);
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${output}/city.png` });
  await page.mouse.click(1050, 600);
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${output}/build.png` });
  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${output}/build_closed.png` });
  await page.setViewportSize({ width: 640, height: 480 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${output}/narrow.png` });
  assert.deepEqual(errors, [], "Game boot and input must not log browser/engine errors");

  const checks = await page.evaluate(() => {
    const checks = [];
    const check = (pass, name) => checks.push({ name, pass: Boolean(pass) });
    const path = name => `res://assets/ui/rive/citybuilder_${name}.riv`;
    const fixtures = [
      ["main_menu", "MainMenu", "MainMenu", "Play_Slot", 1152, 648],
      ["build_menu", "BuildMenu", "BuildMenu", "ContentSlot", 600, 360],
      ["build_menu", "BuildButton", "BuildButton", "HitSlot", 144, 56],
      ["build_menu", "BuildCard", "BuildButton", "PortraitSlot", 140, 140],
      ["build_menu", "BuildText", "BuildText", "TextSlot", 320, 48],
      ["city_instruments", "CityInstruments", "CityInstruments", "TreasurySlot", 520, 72],
      ["inspect_card", "InspectHeader", "InspectHeader", "CloseSlot", 396, 160],
      ["inspect_card", "InspectService", "InspectService", "IconSlot", 396, 44],
      ["inspect_card", "InspectProgress", "InspectProgress", "ProgressTrack", 396, 16],
      ["inspect_card", "InspectAction", "InspectAction", "HitSlot", 120, 56],
      ["milestones", "MilestoneSummary", "MilestoneSummary", "Surface", 560, 112],
      ["milestones", "MilestoneRow", "MilestoneRow", "Surface", 560, 120],
      ["milestones", "MilestoneCelebration", "MilestoneCelebration", "Surface", 440, 104],
    ];
    const baseline = CityRive.diagnostics().surfaces;
    for (const [file, artboard, machine, slot, width, height] of fixtures) {
      const initial = file === "milestones"
        ? { reducedMotion: true, reveal: 1, motionSeconds: 0, revealSeconds: 0 }
        : { reducedMotion: true };
      const surface = CityRive.createSurface(path(file), artboard, machine, JSON.stringify(initial));
      check(surface !== null, `${artboard}: loads`);
      if (!surface) continue;
      for (const w of [width, Math.max(120, Math.round(width * 0.65))]) {
        check(surface.resize(w, height), `${artboard}/${w}: resize`);
        for (let i = 0; i < 30; i++) surface.advance(0.1);
        const bounds = JSON.parse(surface.layoutRect(slot));
        check(bounds?.length === 4 && bounds.every(Number.isFinite) && bounds[2] > 0 && bounds[3] > 0,
          `${artboard}/${w}: named layout`);
        const pixels = surface.pixels();
        check(pixels?.length === w * height * 4, `${artboard}/${w}: RGBA size`);
        check(pixels?.some((value, index) => index % 4 === 3 && value > 0), `${artboard}/${w}: visible`);
        const renders = surface.renderCount;
        for (let i = 0; i < 60; i++) surface.advance(0.1);
        check(surface.renderCount === renders, `${artboard}/${w}: no idle redraw`);
      }
      const renders = surface.renderCount;
      check(surface.setValue("boolean", "reducedMotion", true), `${artboard}: boolean binding`);
      check(!surface.advance(-1) && !surface.advance(NaN), `${artboard}: invalid deltas`);
      check(!surface.resize(0, height) && !surface.resize(4097, height), `${artboard}: invalid sizes`);
      check(!surface.setValue("number", "reducedMotion", 1), `${artboard}: wrong property type`);
      check(!surface.setValue("number", "progress", Infinity), `${artboard}: nonfinite values`);
      check(JSON.parse(surface.layoutRect("missing-slot")) === null, `${artboard}: missing slot`);
      surface.advance(0.1);
      check(surface.renderCount === renders, `${artboard}: unchanged/rejected values stay idle`);
      surface.dispose();
      surface.dispose();
    }
    const a = CityRive.createSurface(path("main_menu"), "MainMenu", "MainMenu", '{"reducedMotion":true}');
    const b = CityRive.createSurface(path("main_menu"), "MainMenu", "MainMenu", '{"reducedMotion":true}');
    check(a.setValue("string", "buttonLabel", "Browser test"), "Text binding accepted");
    check(a.getValue("string", "buttonLabel", "") === "Browser test", "Text binding readback");
    check(b.getValue("string", "buttonLabel", "") !== "Browser test", "Instances do not share VM state");
    a.resize(640, 360);
    for (let i = 0; i < 30; i++) a.advance(0.1);
    const pixels = a.pixels();
    check(pixels.some((v, i) => i % 4 === 3 && v === 0), "Transparent background");
    check(pixels.some((v, i) => i % 4 === 3 && v > 0 && v < 255), "Antialiased alpha");
    a.dispose(); b.dispose();
    const progress = CityRive.createSurface(path("milestones"), "MilestoneRow", "MilestoneRow",
      '{"reducedMotion":true,"motionSeconds":0,"progress":0.25}');
    check(progress.getValue("number", "progress", -1) === 0.25, "Initial number binding");
    check(progress.setValue("number", "progress", 0.75), "Number binding update");
    check(progress.getValue("number", "progress", -1) === 0.75, "Number binding readback");
    progress.advance(0.1);
    progress.dispose();
    // These failures are expected. They must not leak partially created WASM objects.
    for (let i = 0; i < 10; i++) {
      check(CityRive.createSurface(path("main_menu"), "missing", "MainMenu", "{}") === null,
        `Invalid artboard ${i}`);
      check(CityRive.createSurface(path("main_menu"), "MainMenu", "MainMenu", '{"invalid":true}') === null,
        `Invalid initial property ${i}`);
    }
    check(CityRive.diagnostics().surfaces === baseline, "Teardown restores live surface count");
    return checks;
  });
  await writeFile(`${output}/checks.json`, JSON.stringify(checks, null, 2));
  const unexpected = errors.filter(error => !error.startsWith("Rive surface: Missing Rive artboard:") &&
    !error.startsWith("Rive surface: Invalid initial view model property:"));
  assert.deepEqual(unexpected, [], "No unexpected errors during the surface probe");
  assert.deepEqual(checks.filter(check => !check.pass), [], "All surface checks pass");
  console.log(`${checks.length} checks passed; screenshots in ${output}`);
} finally {
  await browser.close();
}
