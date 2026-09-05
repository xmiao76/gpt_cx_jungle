import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';

// Each validation command owns an ephemeral server unless a URL is supplied.
// It never relies on a developer having left Vite running in another terminal.
export async function localSite() {
  if (process.env.JUNGLE_URL) return { url: process.env.JUNGLE_URL, close() {} };
  const child = spawn(process.execPath, ['scripts/static-server.mjs'], {
    windowsHide: true, stdio: ['ignore', 'pipe', 'inherit'], env: { ...process.env, PORT: '0' },
  });
  try {
    const url = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Static test server did not start.')), 10000);
      const lines = createInterface({ input: child.stdout });
      child.once('error', error => { clearTimeout(timer); reject(error); });
      child.once('exit', code => { clearTimeout(timer); reject(new Error('Static test server exited: ' + code)); });
      lines.on('line', line => {
        try {
          const data = JSON.parse(line);
          if (data.url) { clearTimeout(timer); lines.close(); resolve(data.url); }
        } catch { /* Ignore unrelated startup output. */ }
      });
    });
    return { url, close() { child.kill(); } };
  } catch (error) { child.kill(); throw error; }
}
