import Sf from 'https://cdn.jsdelivr.net/npm/@lichess-org/stockfish-web@0.3.0/sf_18_smallnet.js';
const BASE = 'https://cdn.jsdelivr.net/npm/@lichess-org/stockfish-web@0.3.0/';
let engine = null;
(async () => {
  try {
    engine = await Sf({ locateFile: p => BASE + p, listen: l => self.postMessage(l) });
    self.postMessage('sf_ready');
  } catch(e) {
    self.postMessage('sf_error:' + e.message);
  }
})();
self.onmessage = e => { if (engine) engine.uci(e.data); };
