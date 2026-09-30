/**
 * DAIRE — Off-Chain Score Engine (STEP 2, njia ya pili)
 *
 * HESABU HII NI KAMA ILE ILIYO NDANI YA DaireCreditScore.sol — TANO (5)
 * dimensions, uzito 30/20/15/20/15, min-max 300-850. Input ni features
 * zilezile zinazotumwa kwenye contract, hivyo matokeo yanapaswa kulingana
 * kabisa na `previewScore` ya contract.
 *
 * KANUNI ZA SOLIDITY ZILIZOIGWA HAPA:
 *  - Hakuna float: asilimia ni basis points (9500 = 95.00%).
 *  - GAWANYA MWISHO KABISA: (a * b) / c, siyo (a / c) * b.
 *  - Months since adverse 65535 (NEVER) = hakuna tukio baya kamwe.
 */

// --- Uzito wa dimensions (lazima jumla iwe 100) ---
// Lazima zilingane na W_D1..W_D5 za DaireCreditScore.sol.
const WEIGHTS = {
  paymentReliability: 30,       // D1 — 30%
  financialStability: 20,       // D2 — 20%
  creditDebtManagement: 15,     // D3 — 15%
  behaviouralConsistency: 20,   // D4 — 20%
  trustEvidence: 15             // D5 — 15%
};

const MIN_SCORE = 300;
const MAX_SCORE = 850;
const BPS = 10000;
const NEVER = 65535;

// --- Gates za utoshelevu wa ushahidi (BR-10) ---
const MIN_HISTORY_MONTHS = 6;
const MIN_BEHAVIOUR_EVENTS = 8;
const MIN_REPAYMENT_RECORDS = 1;
const MIN_VERIFIED_SOURCES = 1;

const MISSING_HISTORY = 1;    // 0001
const MISSING_EVENTS = 2;     // 0010
const MISSING_REPAYMENTS = 4; // 0100
const MISSING_VERIFIED = 8;   // 1000

const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);

/**
 * Mgawanyo wa nambari kamili kama EVM (SDIV/DIV): unakata movi kuelekea
 * sifuri. Math.floor ingesababisha tofauti na Solidity kwenye namba hasi
 * (mfano trendBps). HII NDIYO SIRI YA PARITY KAMILI.
 */
const ediv = (a, b) => Math.trunc(a / b);

/** D1 — Payment Reliability (uzito 30%). Angalia scoreD1() ya contract. */
function scoreD1(f) {
  let pts;
  if      (f.onTimeRatioBps >= 9800) pts = 100;
  else if (f.onTimeRatioBps >= 9500) pts = 85;
  else if (f.onTimeRatioBps >= 9000) pts = 70;
  else if (f.onTimeRatioBps >= 8000) pts = 50;
  else if (f.onTimeRatioBps >= 6000) pts = 28;
  else                               pts = 10;

  // Ukali wa ucheleweshaji: -2 kwa kila siku 10, kikomo -20
  pts -= Math.min(ediv(f.maxDaysLate, 10) * 2, 20);

  // Marejesho yaliyokosekana: -6 kila moja, kikomo -30
  pts -= Math.min(f.missedCount * 6, 30);

  // Mfululizo mzuri wa miezi 12+: +5
  if (f.onTimeStreak >= 12) pts += 5;

  return clamp(pts, 0, 100);
}

/** D2 — Financial Stability (uzito 20%). Angalia scoreD2() ya contract. */
function scoreD2(f) {
  const continuity = ediv(40 * f.activeMonthsBps, BPS);
  const regularity = ediv(30 * f.regularMonthsBps, BPS);
  const stability  = ediv(30 * f.balanceStabilityBps, BPS);
  return clamp(continuity + regularity + stability, 0, 100);
}

/** D3 — Credit and Debt Management (uzito 15%). Angalia scoreD3() ya contract. */
function scoreD3(f) {
  let pts = 100;

  pts -= Math.min(f.defaultCount * 35, 70);   // default: -35 kila moja
  pts += Math.min(f.completedCount * 10, 20); // completed: +10 kila moja

  // Matumizi ya mkopo: 30%-70% ni eneo zuri
  if      (f.utilizationBps > 9000) pts -= 25;
  else if (f.utilizationBps > 7000) pts -= 15;
  else if (f.utilizationBps >= 3000) pts -= 0;
  else                               pts += 5;

  // Kukopa taasisi nyingi kwa wakati mmoja
  if      (f.activeLenderCount >= 4) pts -= 20;
  else if (f.activeLenderCount === 3) pts -= 10;

  return clamp(pts, 0, 100);
}

/** Adhabu ya tukio baya: 40 x 0.5^(miezi/12), interpolated kila mwaka. */
function adversePenalty(monthsSince) {
  if (monthsSince === NEVER) return 0;
  const h = Math.floor(monthsSince / 12);
  if (h >= 6) return 0;
  const hi = 40 >> h;         // thamani mwanzoni mwa mwaka h
  const lo = 40 >> (h + 1);   // thamani mwanzoni mwa mwaka h+1
  const r = monthsSince % 12;
  return hi - ediv((hi - lo) * r, 12);
}

/** D4 — Behavioural Consistency (uzito 20%). Angalia scoreD4() ya contract. */
function scoreD4(f) {
  let pts = 60;
  pts += ediv(f.trendBps * 30, BPS);            // mwelekeo: +/- 30
  pts -= ediv(20 * f.volatilityBps, BPS);       // kuyumba: hadi -20
  pts -= adversePenalty(f.monthsSinceAdverse);           // tukio baya la mwisho
  return clamp(pts, 0, 100);
}

/** D5 — Verified Trust Evidence (uzito 15%). Angalia scoreD5() ya contract. */
function scoreD5(f) {
  // Urefu wa historia: hadi 35, kilele miezi 36
  const months = Math.min(f.historyMonths, 36);
  const span = ediv(35 * months, 36);

  // Uwiano wa vyanzo vilivyothibitishwa: hadi 30
  let verif = 0;
  if (f.distinctSourceCount > 0) {
    const v = Math.min(f.verifiedSourceCount, f.distinctSourceCount);
    verif = ediv(30 * v, f.distinctSourceCount);
  }

  // Upana wa vyanzo: hadi 25
  let breadth = 0;
  if      (f.distinctSourceCount >= 3) breadth = 25;
  else if (f.distinctSourceCount === 2) breadth = 20;
  else if (f.distinctSourceCount === 1) breadth = 10;

  // Uthibitisho wa vyanzo huru: hadi 10, kilele kwenye wastani 3.00
  const corr = ediv(10 * Math.min(f.meanCorroborationX100, 300), 300);

  // Migongano ambayo haijatatuliwa: -10 kila mmoja, kikomo -25
  const conflicts = Math.min(f.openConflictCount * 10, 25);

  return clamp(span + verif + breadth + corr - conflicts, 0, 100);
}

/**
 * Kagua gates za ushahidi (BR-10). Sawa na checkSufficiency() ya contract.
 * @returns {number} missingMask — 0 = data zinatosha.
 */
function checkSufficiency(f) {
  let mask = 0;
  if (f.historyMonths        < MIN_HISTORY_MONTHS)    mask |= MISSING_HISTORY;
  if (f.behaviourEventCount  < MIN_BEHAVIOUR_EVENTS)  mask |= MISSING_EVENTS;
  if (f.repaymentRecordCount < MIN_REPAYMENT_RECORDS) mask |= MISSING_REPAYMENTS;
  if (f.verifiedSourceCount  < MIN_VERIFIED_SOURCES)  mask |= MISSING_VERIFIED;
  return mask;
}

/** Maelezo ya missingMask kwa lugha ya binadamu (sawa na explainMissing). */
function explainMissing(mask) {
  if (mask === 0) return "Ushahidi unatosha";
  const parts = [];
  if (mask & MISSING_HISTORY)    parts.push("historia<6mwezi");
  if (mask & MISSING_EVENTS)     parts.push("matukio<8");
  if (mask & MISSING_REPAYMENTS) parts.push("marejesho<1");
  if (mask & MISSING_VERIFIED)   parts.push("vyanzoVERIFIED<1");
  return "INSUFFICIENT_EVIDENCE: " + parts.join(", ");
}

/**
 * Hesabu dimension tano (0-100) kutoka kwenye features zilizokokotolewa.
 * @returns {{d1:number,d2:number,d3:number,d4:number,d5:number}}
 */
function deriveDimensions(f) {
  return {
    d1: scoreD1(f),
    d2: scoreD2(f),
    d3: scoreD3(f),
    d4: scoreD4(f),
    d5: scoreD5(f)
  };
}

/**
 * Geuza dimension tano kuwa SINGLE SCORE ya 300-850.
 * weightedSum ya juu kabisa = (30+20+15+20+15) x 100 = 10,000.
 * S = 300 + (weightedSum x 550) / 10000   (min-max transformation)
 */
function calculateCreditScore(dims) {
  const weightedSum =
    dims.d1 * WEIGHTS.paymentReliability +
    dims.d2 * WEIGHTS.financialStability +
    dims.d3 * WEIGHTS.creditDebtManagement +
    dims.d4 * WEIGHTS.behaviouralConsistency +
    dims.d5 * WEIGHTS.trustEvidence;

  return clamp(
    Math.trunc(MIN_SCORE + (weightedSum * (MAX_SCORE - MIN_SCORE)) / 10000),
    MIN_SCORE,
    MAX_SCORE
  );
}

/**
 * Band ya FICO kutoka kwenye score. KANUNI: dimension yoyote < 40
 * inazuia band kuwa bora kuliko FAIR (sawa na riskBandOf ya contract).
 *
 * @param {number} score - 300-850
 * @param {number|null} minDimension - dimension ndogo zaidi (null = 100)
 * @returns {string} POOR | FAIR | GOOD | VERY_GOOD | EXCEPTIONAL
 */
function bandOfScore(score, minDimension) {
  let band;
  if      (score < 580) band = "POOR";
  else if (score < 670) band = "FAIR";
  else if (score < 740) band = "GOOD";
  else if (score < 800) band = "VERY_GOOD";
  else                        band = "EXCEPTIONAL";

  const minDim = minDimension === null || minDimension === undefined ? 100 : minDimension;
  if (minDim < 40 && (band === "GOOD" || band === "VERY_GOOD" || band === "EXCEPTIONAL")) {
    band = "FAIR";
  }
  return band;
}

/**
 * Njia kamili ya off-chain: features -> gates -> dimensions -> single score.
 * @returns {{ok:boolean, missingMask?:number, reason?:string,
 *            dimensions?:object, finalScore?:number, band?:string}}
 */
function evaluateOffChain(f) {
  const missingMask = checkSufficiency(f);
  if (missingMask !== 0) {
    return { ok: false, missingMask, reason: explainMissing(missingMask) };
  }

  const dimensions = deriveDimensions(f);
  const finalScore = calculateCreditScore(dimensions);

  const minDim = Math.min(dimensions.d1, dimensions.d2, dimensions.d3,
                          dimensions.d4, dimensions.d5);
  const band = bandOfScore(finalScore, minDim);

  return { ok: true, dimensions, finalScore, band, missingMask: 0 };
}

module.exports = {
  WEIGHTS,
  deriveDimensions,
  calculateCreditScore,
  bandOfScore,
  evaluateOffChain,
  checkSufficiency,
  explainMissing
};
