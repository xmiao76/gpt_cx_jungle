import { describe, expect, it } from 'vitest';
import { newestSnapshot } from './revision';
import type { Snapshot } from './types';
const snapshot = (revision: number) => ({ revision }) as Snapshot;
describe('authoritative snapshot ordering', () => {
  it('accepts initialization and newer replies', () => {
    const first = snapshot(1), next = snapshot(2);
    expect(newestSnapshot(null, first)).toBe(first);
    expect(newestSnapshot(first, next)).toBe(next);
  });
  it('does not overwrite a newer state with a delayed command reply', () => {
    const current = snapshot(20);
    expect(newestSnapshot(current, snapshot(19))).toBe(current);
  });
  it('orders revisions correctly at the u32 wrap boundary', () => {
    const before = snapshot(0xffffffff), after = snapshot(0);
    expect(newestSnapshot(before, after)).toBe(after);
    expect(newestSnapshot(after, before)).toBe(after);
  });
});
