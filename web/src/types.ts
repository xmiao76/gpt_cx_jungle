export type Side = 'blue' | 'red';
export type Difficulty = 'easy' | 'medium' | 'hard';
export interface Settings { human: Side; difficulty: Difficulty; mode: 'human' | 'watch' }
export interface Position { board: number[]; side: Side; quiet: number }
export interface Move { from: number; to: number; capture: number; jump: boolean }
export interface Outcome { kind: string; winner: Side | null; message: string }
export interface HistoryMove extends Move { piece: number; notation: string }
export interface Snapshot {
  protocol_version: 1; revision: number; version: string; rules_id: string;
  position: Position; legal_moves: Move[]; outcome: Outcome; history: HistoryMove[];
  cursor: number; captured: number[]; settings: Settings; can_undo: boolean; can_redo: boolean;
  terrain: { kind: 'land' | 'water' | 'trap' | 'den'; owner: Side | null }[];
}
export interface SearchResult {
  best_move: Move | null; depth: number; score: number; nodes: number; elapsed_ms: number;
  pv: Move[]; tt_hits: number; tablebase_hits?: number; aborted: boolean; profile: string;
}
export interface SearchOptions {
  difficulty?: Difficulty; time_ms?: number; node_limit?: number; profile?: string; max_depth?: number;
}
export interface EngineModule {
  default: (options: { module_or_path: WebAssembly.Module | BufferSource | string }) => Promise<unknown>;
  Engine: new () => { dispatch: (request: string) => string; free: () => void };
  search: (position: string, options: string, progress: (json: string) => void) => string;
  inspect: (position: string) => string;
}
export type Command =
  | { type: 'snapshot' }
  | { type: 'undo' }
  | { type: 'redo' }
  | { type: 'export' }
  | { type: 'new' | 'settings'; settings: Settings }
  | { type: 'move'; from: number; to: number; revision: number }
  | { type: 'import'; contents: string };
export const ANIMALS = ['', 'Rat', 'Cat', 'Dog', 'Wolf', 'Leopard', 'Tiger', 'Lion', 'Elephant'];
export const RESPONSE_MS: Record<Difficulty, number> = { easy: 100, medium: 500, hard: 2000 };
export function animalUrl(piece: number): string {
  return new URL('animals/' + (piece > 0 ? 'blue' : 'red') + '_' + ANIMALS[Math.abs(piece)].toLowerCase() + '.png', document.baseURI).href;
}
