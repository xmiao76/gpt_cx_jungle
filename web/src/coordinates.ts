export function displaySquare(square: number, flipped: boolean): number { return flipped ? 62 - square : square; }
export function pointerSquare(x: number, y: number, width: number, height: number, flipped: boolean): number | null {
  if (width <= 0 || height <= 0 || x < 0 || y < 0 || x >= width || y >= height) return null;
  const view = Math.floor(y * 9 / height) * 7 + Math.floor(x * 7 / width);
  return displaySquare(view, flipped);
}
export function squareName(square: number): string { return String.fromCharCode(97 + square % 7) + (9 - Math.floor(square / 7)); }
