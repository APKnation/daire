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

const DATA = loadData();
const BY_REF = new Map();
DATA.forEach((b) => BY_REF.set(String(b.borrower_reference), b));

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
        // If this lender does not own the reference, still log the attempt
        // and reply 404, exactly like a real data subsystem.
        if (!BY_REF.has(borrower_reference)) {
          const errBody = JSON.stringify({
            received: false,
            lender_system: LENDER_SYSTEM,
            error: 'BORROWER_NOT_FOUND',
            borrower_reference,
          });
          res.writeHead(404, {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(errBody),
            'Access-Control-Allow-Origin': '*',
          });
          res.end(errBody);
          return;
        }

        _ack(res, borrower_reference, central_borrower_reference, payload.result ?? payload.results ?? null);
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

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not Found' }));
});

srv.listen(PORT, HOST, () => console.log('manual borrower server listening on', HOST, PORT));
