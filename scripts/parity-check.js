import hre from "hardhat";
import { createRequire } from "module";

const require = createRequire(import.meta.url);
const { evaluateOffChain } = require("../daire-middleware/scoreEngine.js");

// Seed data (seed_data.txt) — mkopaji mmoja wa majaribio
const SEED_FEATURES = {
  historyMonths: 12,
  behaviourEventCount: 25,
  repaymentRecordCount: 10,
  verifiedSourceCount: 2,
  onTimeRatioBps: 9500,
  maxDaysLate: 0,
  missedCount: 0,
  onTimeStreak: 10,
  activeMonthsBps: 10000,
  regularMonthsBps: 9000,
  balanceStabilityBps: 8000,
  defaultCount: 0,
  completedCount: 2,
  utilizationBps: 3000,
  activeLenderCount: 1,
  trendBps: 500,
  volatilityBps: 1000,
  monthsSinceAdverse: 65535,
  distinctSourceCount: 2,
  meanCorroborationX100: 250,
  openConflictCount: 0
};

// Random edge cases — namba hasi, mipaka ya juu/chini, tukio baya karibu
const EDGE_CASES = [
  { ...SEED_FEATURES, onTimeRatioBps: 9999, maxDaysLate: 35, missedCount: 7, onTimeStreak: 12 },
  { ...SEED_FEATURES, onTimeRatioBps: 5500, maxDaysLate: 120, missedCount: 9, onTimeStreak: 0 },
  { ...SEED_FEATURES, trendBps: -10000, volatilityBps: 10000, monthsSinceAdverse: 3 },
  { ...SEED_FEATURES, trendBps: 10000, volatilityBps: 0, monthsSinceAdverse: 72 },
  { ...SEED_FEATURES, historyMonths: 36, distinctSourceCount: 5, verifiedSourceCount: 5, meanCorroborationX100: 300 },
  { ...SEED_FEATURES, defaultCount: 5, completedCount: 9, utilizationBps: 9500, activeLenderCount: 6 },
  { ...SEED_FEATURES, activeMonthsBps: 1234, regularMonthsBps: 5678, balanceStabilityBps: 9999 },
  { ...SEED_FEATURES, monthsSinceAdverse: 13, trendBps: -750, utilizationBps: 2999 }
];

async function main() {
  const { ethers } = await hre.network.getOrCreate();
  const daire = await ethers.deployContract("DaireCreditScore");

  const cases = [SEED_FEATURES, ...EDGE_CASES];
  let failures = 0;

  for (let i = 0; i < cases.length; i++) {
    const f = cases[i];

    // --- NJIA YA 1: on-chain (contract inahesabu) ---
    const onChain = await daire.previewScore.staticCall(f);

    // --- NJIA YA 2: off-chain (JS engine inahesabu) ---
    const off = evaluateOffChain(f);

    const onScore = Number(onChain.score);
    const match =
      off.ok &&
      onScore === off.finalScore &&
      Number(onChain.d1) === off.dimensions.d1 &&
      Number(onChain.d2) === off.dimensions.d2 &&
      Number(onChain.d3) === off.dimensions.d3 &&
      Number(onChain.d4) === off.dimensions.d4 &&
      Number(onChain.d5) === off.dimensions.d5 &&
      Number(onChain.band) === bandIndex(off.band);

    if (!match) failures++;
    console.log(
      `case ${String(i).padStart(2)}: on-chain=${onScore} band=${onChain.band} | ` +
      `off-chain=${off.ok ? off.finalScore : "INSUFFICIENT"} band=${off.band ?? "-"} | ` +
      (match ? "MATCH ✅" : "MISMATCH ❌")
    );
  }

  // --- full E2E: submitCalculatedScore na off-chain values, kisha getScore ---
  const off = evaluateOffChain(SEED_FEATURES);
  const ref = ethers.keccak256(ethers.toUtf8Bytes("NIDA-19950812-12345-00001|DAIRE_TANZA_SALT_2026"));
  const d = off.dimensions;
  const version = await daire.submitCalculatedScore.staticCall(ref, off.finalScore, d.d1, d.d2, d.d3, d.d4, d.d5);
  await (await daire.submitCalculatedScore(ref, off.finalScore, d.d1, d.d2, d.d3, d.d4, d.d5)).wait();
  const stored = await daire.getScore(ref);
  console.log(
    `\nE2E submitCalculatedScore: version=${version} stored.score=${stored.score} ` +
    `(expected ${off.finalScore}) ${Number(stored.score) === off.finalScore ? "MATCH ✅" : "MISMATCH ❌"}`
  );
  if (Number(stored.score) !== off.finalScore) failures++;

  console.log(failures === 0 ? "\nALL PARITY CHECKS PASSED ✅" : `\n${failures} FAILURE(S) ❌`);
  if (failures > 0) process.exitCode = 1;
}

function bandIndex(band) {
  return { NONE: 0, POOR: 1, FAIR: 2, GOOD: 3, VERY_GOOD: 4, EXCEPTIONAL: 5 }[band] ?? -1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
