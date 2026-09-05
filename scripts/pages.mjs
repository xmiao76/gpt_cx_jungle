import { spawnSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';
import { createHash } from 'node:crypto';
import { run } from './tasks.mjs';
import { sha } from './artifacts.mjs';

const cli = 'node_modules/wrangler/bin/wrangler.js';
function wranglerJson(args) {
  const result = spawnSync(process.execPath, [cli, ...args, '--json'], { encoding: 'utf8', windowsHide: true });
  if (result.status !== 0) throw new Error(result.stderr || 'Wrangler account lookup failed.');
  return JSON.parse(result.stdout);
}
function token() {
  if (process.env.CLOUDFLARE_API_TOKEN) return process.env.CLOUDFLARE_API_TOKEN;
  const paths = [
    process.env.XDG_CONFIG_HOME && join(process.env.XDG_CONFIG_HOME, '.wrangler/config/default.toml'),
    process.env.APPDATA && join(process.env.APPDATA, 'xdg.config/.wrangler/config/default.toml'),
    join(homedir(), '.config/.wrangler/config/default.toml'),
    join(homedir(), '.wrangler/config/default.toml'),
  ].filter(Boolean);
  for (const path of paths) {
    if (!existsSync(path)) continue;
    const match = readFileSync(path, 'utf8').match(/^oauth_token\s*=\s*"([^"\r\n]+)"/m);
    if (match) return match[1];
  }
  throw new Error('Wrangler credentials are unavailable. Run npx wrangler login.');
}
async function api(path, method = 'GET') {
  // Credentials stay in memory and are sent only to the fixed Cloudflare API origin.
  const response = await fetch('https://api.cloudflare.com/client/v4' + path, {
    method, headers: { authorization: 'Bearer ' + token() }, signal: AbortSignal.timeout(30000),
  });
  const data = await response.json();
  if (!response.ok || !data.success) throw new Error('Cloudflare API ' + response.status + ': ' + (data.errors || []).map(e => e.message).join('; '));
  return data.result;
}

export function deploymentSummary(deployment) {
  if (!deployment) return null;
  const metadata = deployment.deployment_trigger?.metadata || {};
  // Deployment responses may contain environment settings. Never persist those
  // in release evidence, including settings from the previous production build.
  return {
    id: deployment.id, url: deployment.url, environment: deployment.environment,
    created_on: deployment.created_on,
    latest_stage: { name: deployment.latest_stage?.name, status: deployment.latest_stage?.status },
    deployment_trigger: { metadata: { branch: metadata.branch, commit_hash: metadata.commit_hash, commit_message: metadata.commit_message } },
  };
}

export async function pagesClient(project) {
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*-jungle$/.test(project)) throw new Error('Invalid derived project name.');
  // This read also lets Wrangler refresh an existing OAuth login before API calls.
  let projects = wranglerJson(['pages', 'project', 'list']);
  if (!projects.some(item => item['Project Name'] === project)) {
    run(process.execPath, [cli, 'pages', 'project', 'create', project, '--production-branch', 'main']);
    projects = wranglerJson(['pages', 'project', 'list']);
  }
  const entry = projects.find(item => item['Project Name'] === project);
  if (!entry?.['Project Domains']?.split(',').map(s => s.trim()).includes(project + '.pages.dev')) {
    throw new Error('Cloudflare assigned a different subdomain. Choose a different model_base_name; the naming scheme will not be changed silently.');
  }
  const listed = wranglerJson(['pages', 'deployment', 'list', '--project-name', project]);
  const dashboard = listed.map(item => item.Build?.match(/^https:\/\/dash\.cloudflare\.com\/([a-f0-9]{32})\//)?.[1]).find(Boolean);
  let account = process.env.CLOUDFLARE_ACCOUNT_ID || dashboard;
  if (!account) {
    const accounts = await api('/accounts');
    if (accounts.length !== 1) throw new Error('Multiple authorized Cloudflare accounts are available. Select the intended account in Wrangler before deploying.');
    account = accounts[0].id;
  }
  if (!/^[a-f0-9]{32}$/.test(account)) throw new Error('Cannot resolve the authorized Pages account.');
  const path = '/accounts/' + account + '/pages/projects/' + project;
  const current = async () => deploymentSummary((await api(path)).canonical_deployment);
  return {
    current,
    async upload(branch, message) {
      // The unique release message lets us distinguish our upload from a concurrent one.
      const before = new Set(wranglerJson(['pages', 'deployment', 'list', '--project-name', project]).map(item => item.Id));
      run(process.execPath, [cli, 'pages', 'deploy', 'dist/web', '--project-name', project, '--branch', branch, '--commit-dirty=true', '--commit-message', message]);
      const deployments = await api(path + '/deployments');
      const ours = deployments.find(item => !before.has(item.id) && item.deployment_trigger?.metadata?.commit_message === message);
      if (!ours || ours.latest_stage?.status !== 'success') throw new Error('Cannot identify a successful upload for this release.');
      return deploymentSummary(ours);
    },
    async rollback(previous, promoted) {
      return guardedRollback(previous, promoted, current, async id => api(path + '/deployments/' + encodeURIComponent(id) + '/rollback', 'POST'));
    },
  };
}

export async function guardedRollback(previous, promoted, current, restore) {
  if (!previous?.id) return { restored: false, reason: 'No previous production deployment exists.' };
  const active = await current();
  if (!promoted?.id || active?.id !== promoted.id) return { restored: false, reason: 'Production changed independently; no rollback was attempted.' };
  await restore(previous.id);
  if ((await current())?.id !== previous.id) throw new Error('Rollback did not restore the previous production deployment.');
  return { restored: true, id: previous.id };
}

export async function verifyHostedArtifact(url) {
  const parsed = new URL(url);
  if (parsed.protocol !== 'https:' || !parsed.hostname.endsWith('.pages.dev')) throw new Error('Release verification expects an HTTPS Pages URL.');
  const checks = [];
  for (const file of ['index.html', 'engine/jungle_wasm.js', 'engine/jungle_wasm_bg.wasm']) {
    const response = await fetch(new URL(file, url + '/'), { cache: 'no-store', signal: AbortSignal.timeout(30000) });
    if (!response.ok) throw new Error('Deployed asset did not load: ' + file);
    const actual = createHash('sha256').update(Buffer.from(await response.arrayBuffer())).digest('hex');
    if (actual !== sha('dist/web/' + file)) throw new Error('Deployed bytes differ from the validated release: ' + file);
    if (file.endsWith('.wasm') && !response.headers.get('content-type')?.startsWith('application/wasm')) throw new Error('The deployed WebAssembly content type is incorrect.');
    if (file === 'index.html' && !response.headers.get('content-security-policy')?.includes('wasm-unsafe-eval')) throw new Error('The deployed security headers are missing.');
    checks.push({ file, sha: actual, contentType: response.headers.get('content-type') });
  }
  return checks;
}
