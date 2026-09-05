import { describe, expect, it } from 'vitest';
import { displaySquare, pointerSquare } from './coordinates';
describe('board coordinates', () => {
  it('round trips all squares at fractional sizes and both orientations', () => {
    for (const flipped of [false, true]) for (const width of [350, 481.5, 720, 1050]) {
      const height = width * 9 / 7;
      for (let square = 0; square < 63; square++) {
        const view = displaySquare(square, flipped);
        expect(pointerSquare((view % 7 + .5) * width / 7, (Math.floor(view / 7) + .5) * height / 9, width, height, flipped)).toBe(square);
      }
    }
  });
  it('rejects borders and invalid dimensions', () => {
    expect(pointerSquare(-1, 0, 700, 900, false)).toBeNull();
    expect(pointerSquare(700, 900, 700, 900, true)).toBeNull();
    expect(pointerSquare(0, 0, 0, 0, false)).toBeNull();
    expect(pointerSquare(0, 0, 700, 900, true)).toBe(62);
  });
});
