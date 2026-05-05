const CDN = 'https://cdn.jsdelivr.net/npm/stockfish@16.0.0/src/';

// Synchronously fetch the WASM binary from CDN before importScripts runs.
// The script computes its WASM path from scriptDirectory (our GitHub Pages URL → 404),
// but if Module.wasmBinary is already set it skips the URL fetch entirely.
const xhr = new XMLHttpRequest();
xhr.open('GET', CDN + 'stockfish-nnue-16-single.wasm', false); // synchronous
xhr.responseType = 'arraybuffer';
xhr.send();
if (xhr.status !== 200) throw new Error('WASM fetch failed: ' + xhr.status);
const wasmBinary = new Uint8Array(xhr.response);

self.Module = { wasmBinary };
importScripts(CDN + 'stockfish-nnue-16-single.js');

const factory = typeof Stockfish !== 'undefined' ? Stockfish
              : typeof STOCKFISH !== 'undefined' ? STOCKFISH
              : null;
if (!factory) throw new Error('No Stockfish factory found');

let engine = null;
const queue = [];
self.onmessage = e => engine ? engine.postMessage(e.data) : queue.push(e.data);

Promise.resolve(factory({ wasmBinary })).then(eng => {
  engine = eng;
  engine.addMessageListener(l => self.postMessage(l));
  queue.forEach(m => engine.postMessage(m));
  queue.length = 0;
}).catch(err => self.postMessage('sf_error:' + err.message));
