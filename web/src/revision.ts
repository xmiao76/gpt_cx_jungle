import type { Snapshot } from './types';

// A view may receive concurrent command replies out of order. Rust owns state;
// the view only accepts its newest revision, including the u32 wrap boundary.
export function newestSnapshot(current: Snapshot | null, incoming: Snapshot): Snapshot {
  return !current || ((incoming.revision - current.revision) >>> 0) < 0x80000000 ? incoming : current;
}
