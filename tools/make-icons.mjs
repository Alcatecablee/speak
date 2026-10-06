// Renders the PNG app icons from SVG using the locally installed browser.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const out = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'icons');
const glyph = `<g fill="none" stroke="#fff" stroke-width="24" stroke-linecap="round" stroke-linejoin="round">
  <rect x="216" y="150" width="80" height="136" rx="40"/><path d="M176 262a80 80 0 0 0 160 0M256 342v34"/></g>`;
const svgAny = fs.readFileSync(path.join(out, 'icon.svg'), 'utf8');
// Maskable: full-bleed background, glyph shrunk into the 80% safe zone.
const svgMaskable = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" fill="#0d9488"/><g transform="translate(51.2 51.2) scale(0.8)">${glyph}</g></svg>`;

let browser;
for (const channel of ['msedge', 'chrome', undefined]) {
  try { browser = await chromium.launch({ channel }); break; } catch { /* next */ }
}
const page = await browser.newPage();
async function render(svg, size, file) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(`<style>html,body{margin:0;background:transparent}svg{display:block;width:${size}px;height:${size}px}</style>${svg}`);
  await page.screenshot({ path: path.join(out, file), omitBackground: true });
  console.log('wrote', file);
}
await render(svgAny, 192, 'icon-192.png');
await render(svgAny, 512, 'icon-512.png');
await render(svgMaskable, 512, 'icon-maskable-512.png');
await browser.close();
