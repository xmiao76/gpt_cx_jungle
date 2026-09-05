let context: AudioContext | null = null;
export function unlockAudio() {
  try { context ??= new AudioContext(); if (context.state === 'suspended') void context.resume().catch(() => {}); } catch { /* Audio is optional when unavailable. */ }
}
export function playSound(kind: 'move' | 'capture' | 'win', muted: boolean) {
  if (muted || !context || context.state !== 'running') return;
  const frequencies = kind === 'win' ? [523, 659, 784] : kind === 'capture' ? [330, 440] : [420];
  frequencies.forEach((frequency, index) => {
    const oscillator = context!.createOscillator(), gain = context!.createGain();
    const start = context!.currentTime + index * .10;
    oscillator.type = 'sine'; oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(0, start); gain.gain.linearRampToValueAtTime(.10, start + .012);
    gain.gain.exponentialRampToValueAtTime(.001, start + .13);
    oscillator.connect(gain); gain.connect(context!.destination);
    oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
    oscillator.start(start); oscillator.stop(start + .14);
  });
}
