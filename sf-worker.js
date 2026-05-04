const CDN = 'https://cdn.jsdelivr.net/npm/stockfish@16.0.0/src/';
importScripts(CDN + 'stockfish-nnue-16-single.js');

// Export name is Stockfish (capital S), not STOCKFISH
const factory = typeof Stockfish !== 'undefined' ? Stockfish
              : typeof STOCKFISH !== 'undefined' ? STOCKFISH
              : null;
if (!factory) throw new Error('No Stockfish factory found after importScripts');

// Queue messages until the (potentially async) factory resolves
let engine = null;
const queue = [];
self.onmessage = e => engine ? engine.postMessage(e.data) : queue.push(e.data);

Promise.resolve(factory({ locateFile: file => CDN + file })).then(eng => {
  engine = eng;
  engine.addMessageListener(l => self.postMessage(l));
  queue.forEach(m => engine.postMessage(m));
  queue.length = 0;
}).catch(err => self.postMessage('sf_error:' + err.message));
