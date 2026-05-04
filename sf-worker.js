// SF16 NNUE single-thread — served from a real HTTPS URL so Safari can compute scriptDirectory
const CDN = 'https://cdn.jsdelivr.net/npm/stockfish@16.0.0/src/';
self.Module = { locateFile: p => CDN + p };
importScripts(CDN + 'stockfish-nnue-16-single.js');
const engine = STOCKFISH();
engine.addMessageListener(l => self.postMessage(l));
self.onmessage = e => engine.postMessage(e.data);
