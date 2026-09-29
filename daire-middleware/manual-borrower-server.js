const http = require('http');
const { URL } = require('url');
const fs = require('fs');

const PORT = Number(process.env.PORT || 4300);
const HOST = process.env.HOST || '0.0.0.0';
const DATA_FILE = '/data/APKnation/credit/daire-middleware/borrower_mock.json';

const LENDER_SYSTEM = 'DEMO-FLOW';

function loadData() {
  try {
    const raw = fs.readFileSync(DATA_FILE, 'utf8');
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed;
  } catch (e) {}
  return [];
}

// Persisted broker results keyed by borrower_reference. The Central broadcast
// posts result data here, and the lender reads it back through the lender
// API so its UI/dashboard can display credit results.
const BROADCAST_RESULTS = new Map();

function saveData(data) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

function loadResults() {
  try {
    const raw = fs.readFileSync('/data/APKnation/credit/daire-middleware/broadcast_results.json', 'utf8');
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return new Map(parsed.map((r) => [String(r.borrower_reference), r]));
  } catch (e) {}
  return new Map();
}

function saveResults(results) {
  fs.writeFileSync('/data/APKnation/credit/daire-middleware/broadcast_results.json', JSON.stringify(Array.from(results.values()), null, 2));
}

const DATA = loadData();
const BY_REF = new Map();
DATA.forEach((b) => BY_REF.set(String(b.borrower_reference), b));

// Topic emitter: lenders subscribe to a borrower_reference; when Central
// broadcasts a result, the server pushes the fresh result to every
// subscriber so the in-memory lender data is refreshed instantly.
const resultSubscribers = new Map();

function subscribeResults(borrower_reference, callback) {
  if (!resultSubscribers.has(borrower_reference)) {
    resultSubscribers.set(borrower_reference, []);
  }
  resultSubscribers.get(borrower_reference).push(callback);
  // Return the latest stored result immediately so the subscriber can render
  // it while the broadcast may still be in flight.
  return RESULTS.get(borrower_reference) || null;
}

globalThis.__lenderOnResult = (record) => {
  // Refresh the lender's local data for this borrower with the latest
  // values from the broadcast, then notify all subscribers.
  const borrower = BY_REF.get(record.borrower_reference);
  if (borrower && record.result) {
    Object.assign(borrower, {
      score: record.result.credit_score ?? null,
      reputation: record.result.reputation ?? null,
      updated_at: new Date().toISOString(),
    });
    saveData(DATA);
    BY_REF.set(record.borrower_reference, borrower);
  }
  for (const cb of resultSubscribers.get(record.borrower_reference) || []) {
    try { cb(record); } catch (e) {}
  }
};

// Seed previously broadcast results into memory on startup.
const RESULTS = loadResults();

function unsubscribeResults(borrower_reference, callback) {
  const list = resultSubscribers.get(borrower_reference);
  if (!list) return;
  const idx = list.indexOf(callback);
  if (idx !== -1) list.splice(idx, 1);
}

function _ack(res, borrower_reference, central_borrower_reference, result) {
  const body = {
    received: true,
    lender_system: LENDER_SYSTEM,
    result_type: 'CREDIT_RESULT',
    score: result != null && result.credit_score != null ? Number(result.credit_score) : null,
    processed_at: new Date().toISOString(),
    borrower_reference,
    central_borrower_reference,
    lender_customer_id: borrower_reference,
  };
  const raw = JSON.stringify(body);
  res.writeHead(200, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(raw),
    'Access-Control-Allow-Origin': '*',
  });
  res.end(raw);
}

function _storeResult(borrower_reference, central_borrower_reference, result) {
  const record = {
    borrower_reference,
    central_borrower_reference,
    result_type: 'CREDIT_RESULT',
    result,
    lender_system: LENDER_SYSTEM,
    lender_customer_id: borrower_reference,
    received_at: new Date().toISOString(),
  };
  RESULTS.set(borrower_reference, record);
  saveResults(RESULTS);
  return record;
}

const srv = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  const p = url.pathname;

  if (req.method === 'OPTIONS') {
    res.writeHead(200, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'content-type',
    });
    res.end();
    return;
  }

  if (p === '/api/daire/central/receive/' && req.method === 'POST') {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });

    req.on('end', () => {
      try {
        const payload = JSON.parse(body || '{}');
        const borrower_reference = String(payload.borrower_reference ?? '').trim();
        const central_borrower_reference = payload.central_borrower_reference != null
          ? String(payload.central_borrower_reference).trim()
          : null;

        // The lender subsystem only acts on borrowers it actually holds.
        // The broadcast carries NIDA (the lender's global unique customer
        // id) as borrower_reference when the lender holds NIDA for the
        // customer; accept either that or the lender's local customer_id.
        let targetRef = borrower_reference;
        if (BY_REF.has(targetRef)) {
          targetRef = targetRef;
        } else if (BY_REF.has(String(payload.customer_id ?? ''))) {
          targetRef = String(payload.customer_id);
        }
        if (!BY_REF.has(targetRef)) {
          const errBody = JSON.stringify({
            received: false,
            lender_system: LENDER_SYSTEM,
            error: 'BORROWER_NOT_FOUND',
            borrower_reference,
            customer_id: payload.customer_id,
          });
          res.writeHead(404, {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(errBody),
            'Access-Control-Allow-Origin': '*',
          });
          res.end(errBody);
          return;
        }

        // Persist this broadcast result into the lender's own system.
        const stored = _storeResult(
          borrower_reference,
          central_borrower_reference,
          payload.result ?? payload.results ?? null,
        );

        _ack(res, borrower_reference, central_borrower_reference, stored.result);

        // Publish the result to the lender's internal topic/emitter so that
        // any running functions (score calculation, rating update, etc.)
        // are re-invoked with the fresh data.
        if (globalThis.__lenderOnResult) {
          globalThis.__lenderOnResult(stored);
        }
      } catch (err) {
        const errBody = JSON.stringify({ received: false, error: 'INVALID_JSON', message: err.message });
        res.writeHead(400, {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(errBody),
          'Access-Control-Allow-Origin': '*',
        });
        res.end(errBody);
      }
    });
    return;
  }

  if (p === '/borrowers' && req.method === 'GET') {
    const q = url.searchParams;
    let out = DATA;
    if (q.has('borrower_reference')) out = out.filter(x => String(x.borrower_reference) === String(q.get('borrower_reference')));
    if (q.has('id')) out = out.filter(x => String(x.id) === String(q.get('id')));
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(JSON.stringify(out)),
      'Access-Control-Allow-Origin': '*',
    });
    res.end(JSON.stringify(out));
    return;
  }

  if (p.startsWith('/borrowers/') && req.method === 'GET') {
    const ref = decodeURIComponent(p.split('/borrowers/').pop());
    const out = DATA.filter(x => String(x.borrower_reference) === String(ref));
    res.writeHead(out.length ? 200 : 404, {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(JSON.stringify(out)),
      'Access-Control-Allow-Origin': '*',
    });
    res.end(JSON.stringify(out));
    return;
  }

  // GET /api/daire/central/results?borrower_reference=1001
  // Lender reads back the broadcast results it received from Central.
  if (p === '/api/daire/central/results' && req.method === 'GET') {
    const q = url.searchParams;
    const borrower_reference = q.get('borrower_reference');
    if (borrower_reference) {
      const out = Array.from(RESULTS.values()).filter(r => r.borrower_reference === String(borrower_reference));
      res.writeHead(out.length ? 200 : 404, {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(JSON.stringify(out)),
        'Access-Control-Allow-Origin': '*',
      });
      res.end(JSON.stringify(out));
      return;
    }
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(JSON.stringify(Array.from(RESULTS.values()))),
      'Access-Control-Allow-Origin': '*',
    });
    res.end(JSON.stringify(Array.from(RESULTS.values())));
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not Found' }));
});

srv.listen(PORT, HOST, () => console.log('manual borrower server listening on', HOST, PORT));
