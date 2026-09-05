import { spawnSync } from 'node:child_process';
import { readFileSync, mkdirSync, copyFileSync, readdirSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, join } from 'node:path';
const root = resolve(import.meta.dirname, '..');
process.chdir(root);
const node = process.execPath;
export function run(command, args = [], options = {}) {
  const result = spawnSync(command, args, { cwd: root, stdio: 'inherit', ...options });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(command + ' failed (' + result.status + ')');
}
export function metadata() {
  const prompt = readFileSync('prompt_template.md', 'utf8');
  const matches = [...prompt.matchAll(/^- \x60model_base_name = ([a-z0-9]+(?:-[a-z0-9]+)*)\x60/gm)];
  if (matches.length !== 1) throw new Error('Exactly one valid model_base_name is required in the template.');
  const slug = matches[0][1] + '-jungle';
  return { name: 'Jungle', version: '1.0.0', project: slug, url: 'https://' + slug + '.pages.dev' };
}
function assets() {
  mkdirSync('web/public/animals', { recursive: true });
  for (const side of ['blue', 'red']) for (const animal of ['rat', 'cat', 'dog', 'wolf', 'leopard', 'tiger', 'lion', 'elephant']) {
    if (!existsSync(join('web/public/animals', side + '_' + animal + '.png'))) throw new Error('Missing animal artwork: ' + side + ' ' + animal);
  }
  mkdirSync('web/generated', { recursive: true });
  writeFileSync('web/generated/metadata.json', JSON.stringify(metadata(), null, 2));
}
function wasm() {
  run('wasm-pack', ['build', 'wasm', '--target', 'web', '--out-dir', '../artifacts/wasm', '--out-name', 'jungle_wasm', '--release']);
  mkdirSync('web/public/engine', { recursive: true });
  for (const file of ['jungle_wasm.js', 'jungle_wasm_bg.wasm']) copyFileSync(join('artifacts/wasm', file), join('web/public/engine', file));
}
function tauri(args) { run(node, [join(root, 'node_modules/@tauri-apps/cli/tauri.js'), ...args], { cwd: join(root, 'desktop') }); }
const task = process.argv[2];
if (process.argv[1] && resolve(process.argv[1]) === resolve(import.meta.filename)) {
  try {
    switch (task) {
      case 'wasm': wasm(); break;
      case 'dev': assets(); if (!existsSync('web/public/engine/jungle_wasm.js')) wasm(); run(node, ['node_modules/vite/bin/vite.js', '--config', 'vite.config.ts']); break;
      case 'build': assets(); wasm(); run(node, ['node_modules/typescript/bin/tsc', '--noEmit']); run(node, ['node_modules/vite/bin/vite.js', 'build', '--config', 'vite.config.ts']); break;
      case 'desktop-dev': assets(); tauri(['dev']); break;
      case 'desktop-build': tauri(['build']); break;
      case 'test': run('cargo', ['test', '-p', 'jungle-engine', '--release']); run(node, ['node_modules/vitest/vitest.mjs', 'run']); run(node, ['--test', 'scripts/release.test.mjs']); break;
      default: throw new Error('Unknown task: ' + task);
    }
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
