import type { Command, EngineModule, Snapshot, SearchResult, SearchOptions } from './types';
import { RESPONSE_MS } from './types';

export class Cancelled extends Error {}
export class GameClient {
  private readonly instance = Array.from(crypto.getRandomValues(new Uint32Array(4))).join('-');
  readonly native = '__TAURI_INTERNALS__' in window;
  readonly runtime = this.native ? 'Rust · Native' : 'Rust · WebAssembly';
  private engine: InstanceType<EngineModule['Engine']> | null = null;
  private module: WebAssembly.Module | null = null;
  private engineUrl = new URL('engine/jungle_wasm.js', document.baseURI).href;
  private worker: Worker | null = null;
  private workerReady: Promise<void> | null = null;
  private epoch = 0;
  private rejectSearch: ((e: Error) => void) | null = null;
  private unlisten: (() => void) | null = null;
  private nativeProgress: { job: string; update: (result: SearchResult) => void } | null = null;
  private cancelTimer: (() => void) | null = null;
  private searchActive = false;
  private invoke: typeof import('@tauri-apps/api/core').invoke | null = null;

  async initialize(status: (text: string, progress: number) => void): Promise<Snapshot> {
    if (this.native) {
      status('Starting the native engine', 50);
      this.invoke = (await import('@tauri-apps/api/core')).invoke;
      const { listen } = await import('@tauri-apps/api/event');
      this.unlisten = await listen<{ job: string; result: SearchResult }>('search-progress', event => {
        if (this.nativeProgress?.job === event.payload.job) this.nativeProgress.update(event.payload.result);
      });
      const initial = await this.command({ type: 'snapshot' });
      await this.invoke('engine_search', { position: JSON.stringify(initial.position), options: JSON.stringify({ time_ms: 20, max_depth: 1, profile: 'baseline' }), job: this.instance + '-warmup', revision: initial.revision });
    } else {
      status('Loading the shared engine', 10);
      const response = await fetch(new URL('engine/jungle_wasm_bg.wasm', document.baseURI));
      if (!response.ok) throw new Error('Engine download failed (' + response.status + '). Please reload.');
      const buffer = await response.arrayBuffer();
      status('Preparing WebAssembly', 45);
      this.module = await WebAssembly.compile(buffer);
      const module = await import(/* @vite-ignore */ this.engineUrl) as EngineModule;
      await module.default({ module_or_path: this.module });
      this.engine = new module.Engine();
      status('Preparing the AI opponent', 75);
      await this.startWorker();
    }
    status('Ready to play', 100);
    return this.command({ type: 'snapshot' });
  }

  private startWorker(): Promise<void> {
    if (this.native) return Promise.resolve();
    const worker = new Worker(new URL('./search.worker.ts', import.meta.url), { type: 'module' });
    this.worker = worker;
    this.workerReady = new Promise((resolve, reject) => {
      const timeout = window.setTimeout(() => reject(new Error('AI initialization timed out. Reload to retry.')), 10000);
      const listener = (event: MessageEvent) => {
        if (event.data.type === 'ready') { clearTimeout(timeout); worker.removeEventListener('message', listener); resolve(); }
        else if (event.data.type === 'error') { clearTimeout(timeout); reject(new Error(event.data.error)); }
      };
      worker.addEventListener('message', listener);
      worker.addEventListener('error', () => { clearTimeout(timeout); reject(new Error('The AI worker could not load.')); }, { once: true });
      worker.postMessage({ type: 'init', module: this.module, engineUrl: this.engineUrl });
    });
    void this.workerReady.catch(() => {});
    return this.workerReady;
  }

  async command(command: Exclude<Command, { type: 'export' }>): Promise<Snapshot> {
    const result = this.native
      ? await this.invoke!<string>('engine_command', { request: JSON.stringify(command) })
      : this.engine!.dispatch(JSON.stringify(command));
    const snapshot = JSON.parse(result) as Snapshot;
    if (snapshot.protocol_version !== 1) throw new Error('Unsupported engine protocol.');
    return snapshot;
  }

  cancel() {
    const wasActive = this.searchActive;
    const job = this.nativeProgress?.job;
    this.searchActive = false;
    this.epoch++;
    this.cancelTimer?.(); this.cancelTimer = null;
    this.rejectSearch?.(new Cancelled('Search cancelled.'));
    this.rejectSearch = null;
    this.nativeProgress = null;
    if (this.native) { if (this.invoke && wasActive && job) void this.invoke('cancel_search', { job }); }
    else if (this.worker && wasActive) { this.worker.terminate(); this.worker = null; this.workerReady = null; }
  }

  async think(snapshot: Snapshot, progress: (result: SearchResult) => void): Promise<{ snapshot: Snapshot; result: SearchResult; responseMs: number }> {
    const epoch = ++this.epoch, start = performance.now();
    this.searchActive = true;
    let completed = false, accepting = true;
    const budget = RESPONSE_MS[snapshot.settings.difficulty];
    let best: SearchResult = { best_move: snapshot.legal_moves[0] ?? null, depth: 0, score: 0, nodes: 0, elapsed_ms: 0, pv: [], tt_hits: 0, aborted: true, profile: 'candidate' };
    if (!best.best_move) throw new Error('There is no legal AI move.');
    const options: SearchOptions = { difficulty: snapshot.settings.difficulty, time_ms: Math.max(1, budget - 35), profile: 'candidate' };
    const update = (result: SearchResult) => {
      if (epoch !== this.epoch || !accepting) return;
      if (result.best_move && snapshot.legal_moves.some(m => m.from === result.best_move!.from && m.to === result.best_move!.to)) {
        best = result; progress(result);
      }
    };
    await new Promise<void>((resolve, reject) => {
      this.rejectSearch = reject;
      let done = false;
      const finish = () => { if (!done) { done = true; accepting = false; clearTimeout(timer); this.cancelTimer = null; this.rejectSearch = null; resolve(); } };
      const timer = window.setTimeout(finish, Math.max(1, budget - 20));
      this.cancelTimer = () => { done = true; accepting = false; clearTimeout(timer); };
      const launch = async () => {
        if (this.native) {
          const job = this.instance + '-' + epoch;
          if (epoch !== this.epoch || done) return;
          this.nativeProgress = { job, update };
          options.time_ms = Math.max(1, budget - (performance.now() - start) - 35);
          const result = JSON.parse(await this.invoke!<string>('engine_search', { position: JSON.stringify(snapshot.position), options: JSON.stringify(options), job, revision: snapshot.revision })) as SearchResult;
          update(result); completed = true; finish();
        } else {
          await (this.workerReady ?? this.startWorker());
          if (epoch !== this.epoch || done) return;
          const worker = this.worker!;
          const listener = (event: MessageEvent) => {
            if (event.data.id !== epoch || epoch !== this.epoch) return;
            if (event.data.type === 'progress') update(event.data.result);
            if (event.data.type === 'result') { update(event.data.result); completed = true; worker.removeEventListener('message', listener); finish(); }
            if (event.data.type === 'error') { worker.removeEventListener('message', listener); clearTimeout(timer); reject(new Error(event.data.error)); }
          };
          worker.addEventListener('message', listener);
          options.time_ms = Math.max(1, budget - (performance.now() - start) - 35);
          worker.postMessage({ type: 'search', id: epoch, position: snapshot.position, options });
        }
      };
      void launch().catch(error => { clearTimeout(timer); reject(error instanceof Error ? error : new Error(String(error))); });
    });
    if (epoch !== this.epoch) throw new Cancelled();
    this.nativeProgress = null;
    // If the deadline timer won the race, stop expensive work before submitting the move.
    if (!this.native && !completed) { this.worker?.terminate(); this.worker = null; this.workerReady = null; }
    this.searchActive = false;
    const current = await this.command({ type: 'move', from: best.best_move!.from, to: best.best_move!.to, revision: snapshot.revision });
    if (epoch !== this.epoch) throw new Cancelled();
    return { snapshot: current, result: best, responseMs: performance.now() - start };
  }

  async save(): Promise<void> {
    if (this.native) { await this.invoke!('save_game'); return; }
    const data = JSON.parse(this.engine!.dispatch(JSON.stringify({ type: 'export' }))) as { save: string };
    const url = URL.createObjectURL(new Blob([data.save], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'jungle-save.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async open(): Promise<string | null> { return this.native ? this.invoke!<string | null>('open_game') : null; }
  dispose() { this.cancel(); this.unlisten?.(); this.unlisten = null; this.worker?.terminate(); this.worker = null; this.engine?.free(); this.engine = null; }
}
