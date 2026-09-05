/// <reference lib="webworker" />
import type { EngineModule, SearchOptions, Position } from './types';
let engine: EngineModule | null = null;
self.onmessage = async (event: MessageEvent<{ type: string; engineUrl: string; module: WebAssembly.Module; id: number; position: Position; options: SearchOptions }>) => {
  const message = event.data;
  try {
    if (message.type === 'init') {
      engine = await import(/* @vite-ignore */ message.engineUrl) as EngineModule;
      await engine.default({ module_or_path: message.module });
      postMessage({ type: 'ready' });
    } else if (message.type === 'search') {
      if (!engine) throw new Error('Search engine has not initialized.');
      const result = JSON.parse(engine.search(JSON.stringify(message.position), JSON.stringify(message.options), json => {
        postMessage({ type: 'progress', id: message.id, result: JSON.parse(json) });
      }));
      postMessage({ type: 'result', id: message.id, result });
    }
  } catch (error) { postMessage({ type: 'error', id: message.id, error: String(error) }); }
};
