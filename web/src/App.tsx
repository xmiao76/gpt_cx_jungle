import { useEffect, useRef, useState, type ReactNode } from 'react';
import { GameClient, Cancelled } from './client';
import { displaySquare, squareName } from './coordinates';
import { ANIMALS, animalUrl, type Command, type SearchResult, type Settings, type Snapshot } from './types';
import { playSound, unlockAudio } from './audio';
import { newestSnapshot } from './revision';
import metadata from '../generated/metadata.json';

function Dialog({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return <dialog ref={ref} className="dialog" onCancel={event => { event.preventDefault(); close(); }}>
    <header className="dialog-header"><h2>{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={close}>×</button></header>
    {children}
  </dialog>;
}
function NewGame({ settings, start, close }: { settings: Settings; start: (settings: Settings) => void; close: () => void }) {
  const [draft, setDraft] = useState(settings);
  return <Dialog title="A new adventure" close={close}>
    <p className="muted">Choose your side of the river.</p>
    <fieldset><legend>Game mode</legend><div className="choice-grid">
      <button className={draft.mode === 'human' ? 'choice selected' : 'choice'} onClick={() => setDraft({ ...draft, mode: 'human' })}>Play against AI<small>Your next challenge</small></button>
      <button className={draft.mode === 'watch' ? 'choice selected' : 'choice'} onClick={() => setDraft({ ...draft, mode: 'watch' })}>AI vs AI<small>Watch the animals play</small></button>
    </div></fieldset>
    {draft.mode === 'human' && <fieldset><legend>Who moves first?</legend><div className="choice-grid">
      <button className={draft.human === 'blue' ? 'choice selected' : 'choice'} onClick={() => setDraft({ ...draft, human: 'blue' })}>I move first<small>You play Blue</small></button>
      <button className={draft.human === 'red' ? 'choice selected' : 'choice'} onClick={() => setDraft({ ...draft, human: 'red' })}>AI moves first<small>You play Red</small></button>
    </div></fieldset>}
    <label className="field-label">Difficulty<select aria-label="New game difficulty" value={draft.difficulty} onChange={event => setDraft({ ...draft, difficulty: event.target.value as Settings['difficulty'] })}>
      <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
    </select></label>
    <footer className="dialog-actions"><button className="button secondary" onClick={close}>Cancel</button><button className="button primary" onClick={() => start(draft)}>Start game <span aria-hidden="true">↗</span></button></footer>
  </Dialog>;
}
function Help({ close }: { close: () => void }) {
  return <Dialog title="How to play Jungle" close={close}>
    <div className="help-content">
      <p>A game of patience, clever captures, and daring river crossings. Blue always opens; each side moves one animal per turn.</p>
      <h3>Make your move</h3><p>Select one of your animals, then a highlighted square. Dots show empty destinations; outlined animals can be captured. Animals move one square up, down, left, or right. No diagonal moves or passing.</p>
      <h3>Reach the den</h3><p>Win by entering the opposing den or capturing all opposing animals. You also win if the opponent has no legal move. You can never enter your own den.</p>
      <h3>Know your animals</h3><p>An animal captures an equal or lower-ranked opponent by landing on its square. Strongest to weakest:</p>
      <div className="rank-list">{ANIMALS.slice(1).map((name, index) => ({ name, rank: index + 1 })).reverse().map(({ name, rank }) => <div key={name}><span>{rank}</span>{name}</div>)}</div>
      <p><strong>The little exception:</strong> a Rat can capture an Elephant on dry terrain. An Elephant can capture a Rat only when the Rat is in a trap belonging to the Elephant's side.</p>
      <h3>Rivers and jumps</h3><p>Only Rats can enter water. Rats may capture one another in water, but cannot capture across the water/land boundary in either direction.</p>
      <p>Lions jump both across the short width and along the long length of a river. In this game's rule profile, Tigers jump only across the short width (left/right on the unflipped board). A Rat of either color on any square along the river path blocks the jump. A legal jump can end in a capture.</p>
      <h3>Traps and draws</h3><p>Enemy-owned traps reduce an animal's effective rank to zero while it is inside. Your own traps do not weaken your animals. The Rat/Elephant exceptions still apply.</p>
      <p>The game is drawn after 100 consecutive turns without a capture (50 pairs of turns). A capture resets the counter. A win on the same move takes priority. Repetition alone is not a draw.</p>
      <h3>Take your time</h3><p>Undo returns to your previous decision; Redo restores it. In watch mode, Undo and Redo step one move and pause play. Flip board changes only your view. Save and Load carry a game between desktop and browser. Sound can be muted at any time.</p>
      <p className="muted">All rules and AI run on your device. No account is needed to play.</p>
    </div>
  </Dialog>;
}
export default function App() {
  const clientRef = useRef<GameClient | null>(null);
  const [client, setClient] = useState<GameClient | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState({ text: 'Opening the jungle', progress: 0 });
  const [error, setError] = useState('');
  const [thinking, setThinking] = useState(false);
  const [analysis, setAnalysis] = useState<SearchResult | null>(null);
  const [responseMs, setResponseMs] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [flipped, setFlipped] = useState(false);
  const [muted, setMuted] = useState(() => { try { return localStorage.getItem('jungle-muted') === 'true'; } catch { return false; } });
  const [paused, setPaused] = useState(false);
  const [dialog, setDialog] = useState<'new' | 'help' | null>(null);
  const fileRef = useRef<HTMLInputElement>(null), historyRef = useRef<HTMLDivElement>(null);
  const loadPausedRef = useRef(false);
  const soundRef = useRef({ cursor: 0, ended: false });
  const mutedRef = useRef(muted); mutedRef.current = muted;
  useEffect(() => {
    const input = fileRef.current;
    const cancelled = () => setPaused(loadPausedRef.current);
    input?.addEventListener('cancel', cancelled);
    return () => input?.removeEventListener('cancel', cancelled);
  }, [client]);
  useEffect(() => {
    const next = new GameClient(); clientRef.current = next;
    let active = true;
    next.initialize((text, progress) => active && setLoading({ text, progress })).then(state => {
      if (active) { setClient(next); setSnapshot(current => newestSnapshot(current, state)); }
    }).catch(error => active && setError(String(error)));
    return () => { active = false; next.dispose(); };
  }, []);
  useEffect(() => {
    if (!client || !snapshot || paused || snapshot.outcome.kind !== 'ongoing') return;
    if (snapshot.settings.mode !== 'watch' && snapshot.position.side === snapshot.settings.human) return;
    let active = true, finished = false;
    setThinking(true); setSelected(null);
    const start = () => {
      if (!active) return;
      void client.think(snapshot, result => active && setAnalysis(result)).then(({ snapshot: state, result, responseMs }) => {
        if (!active) return;
        finished = true; setThinking(false); setAnalysis(result); setResponseMs(responseMs); setSnapshot(current => newestSnapshot(current, state));
      }).catch(error => {
        if (!active || error instanceof Cancelled) return;
        finished = true; setThinking(false); setPaused(true); setError(String(error));
      });
    };
    // Watch mode has a short, visible beat between moves; this is outside the AI response interval.
    const timer = window.setTimeout(start, snapshot.settings.mode === 'watch' ? 230 : 0);
    return () => { active = false; clearTimeout(timer); if (!finished) client.cancel(); };
  }, [client, snapshot?.revision, paused]);
  useEffect(() => {
    if (!snapshot) return;
    if (snapshot.cursor > soundRef.current.cursor) {
      const last = snapshot.history[snapshot.cursor - 1];
      playSound(snapshot.outcome.kind !== 'ongoing' ? 'win' : last?.capture ? 'capture' : 'move', mutedRef.current);
    }
    soundRef.current = { cursor: snapshot.cursor, ended: snapshot.outcome.kind !== 'ongoing' };
    if (historyRef.current) historyRef.current.scrollTop = historyRef.current.scrollHeight;
  }, [snapshot?.cursor, snapshot?.outcome.kind]);

  async function act(command: Exclude<Command, { type: 'export' }>, pauseWatch = false) {
    if (!client) return;
    unlockAudio(); client.cancel(); setThinking(false); setSelected(null); setError('');
    if (pauseWatch) setPaused(true);
    try { const state = await client.command(command); setSnapshot(current => newestSnapshot(current, state)); return true; } catch (error) { setError(String(error)); return false; }
  }
  function selectSquare(square: number) {
    if (!snapshot || thinking || snapshot.outcome.kind !== 'ongoing' || snapshot.settings.mode === 'watch' || snapshot.position.side !== snapshot.settings.human) return;
    unlockAudio();
    if (selected !== null && snapshot.legal_moves.some(move => move.from === selected && move.to === square)) {
      void act({ type: 'move', from: selected, to: square, revision: snapshot.revision }); return;
    }
    const piece = snapshot.position.board[square];
    setSelected(piece !== 0 && (piece > 0 ? 'blue' : 'red') === snapshot.position.side ? square : null);
  }
  async function load() {
    if (!client) return;
    loadPausedRef.current = paused;
    client.cancel(); setThinking(false); setPaused(true); setError('');
    if (!client.native) { fileRef.current?.click(); return; }
    try { const contents = await client.open(); if (contents !== null) { const imported = await act({ type: 'import', contents }); setPaused(imported ? false : loadPausedRef.current); } else setPaused(loadPausedRef.current); } catch (error) { setError(String(error)); setPaused(loadPausedRef.current); }
  }
  async function loadFile(file?: File) {
    if (!file) return;
    try {
      if (file.size > 4 * 1024 * 1024) throw new Error('Save files must be smaller than 4 MiB.');
      const imported = await act({ type: 'import', contents: await file.text() }); setPaused(imported ? false : loadPausedRef.current);
    } catch (error) { setError(String(error)); setPaused(loadPausedRef.current); }
  }
  if (!snapshot || !client) return <main className="loading-screen">
    <div className="loading-mark">J</div><h1>Jungle</h1><p>{error || loading.text}</p>
    {!error && <progress max={100} value={loading.progress} aria-label="Engine loading progress" />}
    {error && <button className="button primary" onClick={() => location.reload()}>Try again</button>}
    <small>Dou Shou Qi · A game of instinct and strategy</small>
  </main>;
  const { position, outcome } = snapshot;
  const sideName = position.side === 'blue' ? 'Blue' : 'Red';
  const humanTurn = snapshot.settings.mode === 'human' && position.side === snapshot.settings.human;
  const status = outcome.kind !== 'ongoing' ? outcome.winner ? outcome.winner + ' wins' : 'A well-played draw'
    : paused ? 'Game paused' : thinking ? sideName + ' is thinking' : humanTurn ? 'Your move' : sideName + ' to move';
  const legal = snapshot.legal_moves.filter(move => move.from === selected);
  const last = snapshot.cursor > 0 ? snapshot.history[snapshot.cursor - 1] : null;
  return <div className="app" data-testid="app" data-engine-ready="true" data-runtime={client.native ? 'native' : 'wasm'} data-revision={snapshot.revision} data-ply={snapshot.cursor} data-turn={position.side} data-outcome={outcome.kind} data-response-ms={responseMs} data-thinking={thinking}
    onPointerDown={unlockAudio}>
    <header className="app-header">
      <a className="brand" href="#" onClick={event => event.preventDefault()} aria-label="Jungle home"><span className="brand-mark">J<span>✦</span></span><span>Jungle<small>DOU SHOU QI</small></span></a>
      <p className="header-note">A little instinct. A little strategy.</p>
      <nav><button className="header-button" onClick={() => setDialog('help')}>How to play <span aria-hidden="true">↗</span></button>
        <button className="sound-button" aria-label={muted ? 'Unmute sound' : 'Mute sound'} aria-pressed={muted} onClick={() => { setMuted(!muted); try { localStorage.setItem('jungle-muted', String(!muted)); } catch { /* Keep the setting for this session when browser storage is disabled. */ } }}>{muted ? '♪̸' : '♪'}</button></nav>
    </header>
    <main className="game-layout">
      <section className="board-area" aria-label="Game board">
        <div className="turn-bar"><div><span className={'status-light ' + position.side + (thinking ? ' thinking' : '')} />
          <span role="status" aria-live="polite" data-testid="game-status" className="turn-title">{status}</span></div>
          <span className="turn-detail">{outcome.kind === 'ongoing' ? 'Turn ' + (snapshot.cursor + 1) : snapshot.cursor + ' moves played'}</span></div>
        <div className="board-frame"><div className="board" data-testid="board" data-flipped={flipped}>
          {snapshot.terrain.map((terrain, square) => {
            const view = displaySquare(square, flipped), piece = position.board[square], move = legal.find(move => move.to === square);
            const classes = ['square', terrain.kind, terrain.owner || '', selected === square ? 'selected-square' : '', last && [last.from, last.to].includes(square) ? 'last-move' : '', move?.capture ? 'capture-target' : ''].join(' ');
            return <button key={square} data-square={square} data-legal={!!move} className={classes}
              style={{ left: (view % 7 * 100 / 7) + '%', top: (Math.floor(view / 7) * 100 / 9) + '%' }}
              aria-label={squareName(square) + ', ' + (piece ? (piece > 0 ? 'Blue ' : 'Red ') + ANIMALS[Math.abs(piece)] : (terrain.owner ? terrain.owner + ' ' : '') + terrain.kind)}
              aria-pressed={selected === square} onClick={() => selectSquare(square)}>
              {terrain.kind === 'trap' && <span className="terrain-symbol" aria-hidden="true">✧</span>}
              {terrain.kind === 'den' && <span className="den-symbol" aria-hidden="true">⌂<small>DEN</small></span>}
              {move && !move.capture && <span className="move-dot" />}
              {view % 7 === 0 && <span className="row-label">{9 - Math.floor(square / 7)}</span>}
              {Math.floor(view / 7) === 8 && <span className="column-label">{String.fromCharCode(65 + square % 7)}</span>}
            </button>;
          })}
          {position.board.map((piece, square) => {
            if (!piece) return null; const view = displaySquare(square, flipped);
            return <div key={piece} className={'piece ' + (piece > 0 ? 'blue' : 'red') + (selected === square ? 'selected-piece' : '')}
              style={{ transform: 'translate(' + (view % 7 * 100) + '%, ' + (Math.floor(view / 7) * 100) + '%)' }} aria-hidden="true">
              <img src={animalUrl(piece)} alt="" draggable={false}/><span className="piece-label">{ANIMALS[Math.abs(piece)]}</span>
            </div>;
          })}
        </div></div>
        <div className="board-caption"><span className={'side-dot ' + snapshot.settings.human}/>{snapshot.settings.mode === 'watch' ? 'Watching Blue and Red' : 'You play ' + snapshot.settings.human}
          <span>{selected === null ? 'Select an animal, then a highlighted square.' : legal.length ? legal.length + ' legal destinations' : 'No legal moves for this animal.'}</span></div>
        <div className="board-controls">
          <button className="button secondary" onClick={() => setFlipped(!flipped)} aria-pressed={flipped}><span aria-hidden="true">↻</span> Flip board</button>
          <div className="undo-controls"><button className="button secondary" disabled={!snapshot.can_undo} onClick={() => void act({ type: 'undo' }, snapshot.settings.mode === 'watch')}>↶ Undo</button>
            <button className="button secondary" disabled={!snapshot.can_redo} onClick={() => void act({ type: 'redo' }, snapshot.settings.mode === 'watch')}>Redo ↷</button></div>
        </div>
      </section>
      <aside className="sidebar">
        <section className="play-card card">
          <div className="eyebrow">THE NEXT MOVE IS YOURS</div><h1>Into the jungle.</h1><p className="muted">Eight animals. Two dens.<br/>One beautifully wild contest.</p>
          <label className="field-label">AI difficulty<select aria-label="Difficulty" value={snapshot.settings.difficulty}
            onChange={event => void act({ type: 'settings', settings: { ...snapshot.settings, difficulty: event.target.value as Settings['difficulty'] } })}>
            <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
          </select></label>
          <button className="button primary new-game" onClick={() => setDialog('new')}>New game <span aria-hidden="true">↗</span></button>
          {(snapshot.settings.mode === 'watch' || paused && !humanTurn) && outcome.kind === 'ongoing' &&
            <button className="button secondary watch-control" onClick={() => { client.cancel(); setThinking(false); setPaused(!paused); }}>{paused ? 'Resume play' : 'Pause play'}</button>}
          <div className="file-controls"><button onClick={() => void client.save().catch(e => setError(String(e)))}>Save game</button><span>·</span><button onClick={() => void load()}>Load game</button></div>
          <input ref={fileRef} data-testid="load-file" type="file" accept=".json,application/json" hidden onChange={event => { void loadFile(event.target.files?.[0]); event.target.value = ''; }}/>
        </section>
        {outcome.kind !== 'ongoing' && <section className="result-card card" role="alert"><span>✦</span><h2>{outcome.winner ? outcome.winner + ' wins!' : 'A draw'}</h2><p>{outcome.message}</p><button className="button primary" onClick={() => setDialog('new')}>Play again</button></section>}
        {error && <div className="error-card" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}>×</button></div>}
        <section className="history-card card"><div className="card-title"><h2>The story so far</h2><span>{snapshot.cursor} moves</span></div>
          <div className="move-history" ref={historyRef} data-testid="move-history">
            {!snapshot.history.length ? <div className="empty-history"><span>↗</span><p>Every adventure begins<br/>with a first move.</p></div> :
              snapshot.history.map((move, index) => <div key={index} className={'history-row ' + (index >= snapshot.cursor ? 'future' : '')}>
                <span className="move-number">{index + 1}</span><span className={'side-dot ' + (move.piece > 0 ? 'blue' : 'red')}/><span>{move.notation}</span></div>)}
          </div>
          <div className="draw-progress"><span>Since last capture</span><strong>{position.quiet}<small> / 100 turns</small></strong></div>
        </section>
        <section className="captures-card card"><div className="card-title"><h2>Captured animals</h2><span>{snapshot.captured.length}</span></div>
          {snapshot.captured.length ? <div className="captured-list">{snapshot.captured.map(piece => <img key={piece} src={animalUrl(piece)} title={(piece > 0 ? 'Blue ' : 'Red ') + ANIMALS[Math.abs(piece)]} alt={'Captured ' + (piece > 0 ? 'Blue ' : 'Red ') + ANIMALS[Math.abs(piece)]}/>)}</div> : <p className="muted">Everyone is still in the game.</p>}
        </section>
        <details className="engine-details"><summary>Engine details</summary><p>Jungle {snapshot.version} · {client.runtime}</p>
          <p>{analysis ? 'Depth ' + analysis.depth + ' · ' + analysis.nodes.toLocaleString() + ' nodes · ' + responseMs.toFixed(0) + ' ms response' : 'Ready for a little friendly competition.'}</p>
          <p>Rules: {snapshot.rules_id}</p></details>
      </aside>
    </main>
    <footer className="app-footer"><span>Jungle <span>·</span> Dou Shou Qi</span><span>v{metadata.version} <span>·</span> {client.runtime} <span>·</span> Plays entirely on your device</span></footer>
    {dialog === 'new' && <NewGame settings={snapshot.settings} close={() => setDialog(null)} start={settings => { setDialog(null); setPaused(false); setAnalysis(null); setResponseMs(0); void act({ type: 'new', settings }); }}/>}
    {dialog === 'help' && <Help close={() => setDialog(null)}/>}
  </div>;
}
