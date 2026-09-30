const path = require("path");
const fs = require("fs");
const http = require("http");
const crypto = require("crypto");
const express = require("express");
const { ethers } = require("ethers");
const {
    evaluateOffChain,
    calculateCreditScore,
    bandOfScore
} = require("./scoreEngine");

// =====================================================================
// 0. ENV PROFILES — local Hardhat node vs Sepolia
//
//    npm run start:local    -> .env.local   (RPC_URL=http://127.0.0.1:8545)
//    npm run start:sepolia  -> .env.sepolia (RPC_URL_SEPOLIA + HUB_PRIVATE_KEY)
//    npm start              -> .env (legacy, kama ulikuwa unatumia moja)
//
//    ENV_FILE inazidi zote kama umeitaja wewe mwenyewe.
// =====================================================================
const ENV_FILE =
    process.env.ENV_FILE ||
    (process.argv.includes("--env-file")
        ? process.env.npm_config_env_file || process.argv[process.argv.indexOf("--env-file") + 1]
        : null) ||
    (fs.existsSync(path.join(__dirname, ".env.local")) && process.env.DAIRE_PROFILE === "local"
        ? ".env.local"
        : null) ||
    ".env";

require("dotenv").config({
    path: path.isAbsolute(ENV_FILE) ? ENV_FILE : path.join(__dirname, ENV_FILE),
    override: true
});

// --- Thibitisha env kabla ya kuanza (ujumbe za kuvutia, siyo ECONNREFUSED) ---
const REQUIRED_ENV = ["RPC_URL", "HUB_PRIVATE_KEY", "CONTRACT_ADDRESS"];
const missing = REQUIRED_ENV.filter((k) => !process.env[k]);
if (missing.length > 0) {
    console.error("\n[Boot Failed] Missing environment variables: " + missing.join(", "));
    console.error("  Chagua profile:");
    console.error("    npm run start:local    # Hardhat node ya local (:http://172.17.16.70:8545)");
    console.error("    npm run start:sepolia  # Sepolia testnet");
    console.error("  Au weka values moja kwa moja kwenye daire-middleware/.env\n");
    process.exit(1);
}

const app = express();
app.use(express.json());

// =====================================================================
// 1. SMART CONTRACT ABI (Matches DaireCreditScore.sol)
// =====================================================================
const DAIRE_ABI = [
    "function submitFeatures(bytes32 borrowerRef, tuple(uint16 historyMonths, uint16 behaviourEventCount, uint16 repaymentRecordCount, uint8 verifiedSourceCount, uint16 onTimeRatioBps, uint16 maxDaysLate, uint16 missedCount, uint16 onTimeStreak, uint16 activeMonthsBps, uint16 regularMonthsBps, uint16 balanceStabilityBps, uint16 defaultCount, uint16 completedCount, uint16 utilizationBps, uint8 activeLenderCount, int16 trendBps, uint16 volatilityBps, uint16 monthsSinceAdverse, uint8 distinctSourceCount, uint16 meanCorroborationX100, uint8 openConflictCount) f) external returns (uint16 score, uint8 band, uint8 missingMask)",
    "function getScore(bytes32 borrowerRef) external view returns (uint16 score, uint8 band, uint32 assessedAt, uint32 version, bool exists)",
    "function getDimensions(bytes32 borrowerRef) external view returns (uint8 d1, uint8 d2, uint8 d3, uint8 d4, uint8 d5)",
    "function submitCalculatedScore(bytes32 borrowerRef, uint16 finalScore, uint8 d1, uint8 d2, uint8 d3, uint8 d4, uint8 d5) external returns (uint32 version)",
    "function makeBorrowerRef(string identityHash, string salt) external pure returns (bytes32)",
    "function useSubmittedBand() external view returns (bool)",
    "function explainMissing(uint8 missingMask) external pure returns (string)",
    "event ScoreCalculated(bytes32 indexed borrowerRef, address indexed hub, uint16 score, uint8 band, uint32 version, uint32 assessedAt)",
    "event InsufficientEvidence(bytes32 indexed borrowerRef, address indexed hub, uint8 missingMask)",
    "event ScoreRecorded(bytes32 indexed borrowerRef, address indexed hub, uint16 finalScore, uint8 band, uint32 version, uint32 recordedAt)"
];

// Map Solidity RiskBand Enum to Human-Readable Labels
const RISK_BANDS = ["NONE", "POOR", "FAIR", "GOOD", "VERY_GOOD", "EXCEPTIONAL"];

// Maelezo ya missingMask bits (sawa na MISSING_* za contract)
const MISSING_MASK_BITS = [
    { bit: 1, reason: "historia<6mwezi" },
    { bit: 2, reason: "matukio<8" },
    { bit: 4, reason: "marejesho<1" },
    { bit: 8, reason: "vyanzoVERIFIED<1" }
];

function explainMissingMask(mask) {
    if (!mask) return "Ushahidi unatosha";
    const parts = MISSING_MASK_BITS.filter((m) => mask & m.bit).map((m) => m.reason);
    return "INSUFFICIENT_EVIDENCE: " + parts.join(", ");
}

const DIMENSION_KEYS = {
    d1: "d1_paymentReliability",
    d2: "d2_financialStability",
    d3: "d3_debtManagement",
    d4: "d4_behaviouralConsistency",
    d5: "d5_trustEvidence"
};

function dimensionLabels(d) {
    return {
        [DIMENSION_KEYS.d1]: d.d1,
        [DIMENSION_KEYS.d2]: d.d2,
        [DIMENSION_KEYS.d3]: d.d3,
        [DIMENSION_KEYS.d4]: d.d4,
        [DIMENSION_KEYS.d5]: d.d5
    };
}

// =====================================================================
// 1.5 WEBHOOK BROADCAST SUBSYSTEM
//
//     Lender anasajili URL yake; middleware inamsukuma (push) kila matokeo
//     ya contract kwa JSON iliyosainiwa HMAC-SHA256. Hakuna mtu anayelazimika
//     kupoll — anapokea tu.
//
//     Usalama wa webhooks uliyoombwa (docs/API_ENDPOINTS.md §5):
//       * Headers: X-DAIRE-Event, X-DAIRE-Delivery, X-DAIRE-Signature
//       * X-DAIRE-Signature = "sha256=" + HMAC(secret, raw body)
//       * delivery_id ni UUID — consumer inatumia kwa idempotency
//       * Retries: 4 marudio (2s, 8s, 30s, 120s) — ndani ya process
//       * Shindikizo la mwisho linaandikwa kwenye webhooks.failed.json
//
//     Config (env, zote siyo lazima):
//       WEBHOOKS_FILE        (default webhooks.json)   — usajili
//       WEBHOOK_FAILURES_FILE(default webhooks.failed.json) — kumbukumbu za shindikizo
//       WEBHOOK_SECRET       (default: hotgenerated + kiautosave webhooks.secret.json)
//       WEBHOOK_TIMEOUT_MS   (default 5000)
// =====================================================================

const WEBHOOKS_FILE = process.env.WEBHOOKS_FILE
    ? (path.isAbsolute(process.env.WEBHOOKS_FILE) ? process.env.WEBHOOKS_FILE : path.join(__dirname, process.env.WEBHOOKS_FILE))
    : path.join(__dirname, "webhooks.json");

const WEBHOOK_FAILURES_FILE = process.env.WEBHOOK_FAILURES_FILE
    ? (path.isAbsolute(process.env.WEBHOOK_FAILURES_FILE) ? process.env.WEBHOOK_FAILURES_FILE : path.join(__dirname, process.env.WEBHOOK_FAILURES_FILE))
    : path.join(__dirname, "webhooks.failed.json");

const WEBHOOK_TIMEOUT_MS = Math.max(500, parseInt(process.env.WEBHOOK_TIMEOUT_MS || "5000", 10));
const WEBHOOK_RETRY_DELAYS_MS = [2000, 8000, 30000, 120000];
const WEBHOOK_EVENTS = ["SCORE_CALCULATED", "SCORE_RECORDED", "INSUFFICIENT_EVIDENCE"];

// --- Secret: env inazidi zote; kama hakuna, hot-generate na kuhifadhi ---
function loadWebhookSecret() {
    if (process.env.WEBHOOK_SECRET) return process.env.WEBHOOK_SECRET;
    const secretFile = path.join(__dirname, "webhooks.secret.json");
    try {
        const stored = JSON.parse(fs.readFileSync(secretFile, "utf8"));
        if (stored && typeof stored.webhook_secret === "string") {
            return stored.webhook_secret;
        }
    } catch { /* faili haipo — tunaitengeneza chini */ }
    const secret = "whsec_" + crypto.randomBytes(32).toString("hex");
    try {
        fs.writeFileSync(secretFile, JSON.stringify({ webhook_secret: secret }, null, 2) + "\n", { mode: 0o600 });
        console.log(`[Webhooks] Secret mpya imehotgenerate na kuhifadhiwa: ${path.basename(secretFile)}`);
    } catch (err) {
        console.warn(`[Webhooks] Secret haikuweza kuhifadhiwa (${err.message}) — itatengenezwa upya kila boot`);
    }
    return secret;
}

const WEBHOOK_SECRET = loadWebhookSecret();

// --- Usajili: JSON ndogo, inasomeka kwa mkono pia ---
function readWebhooks() {
    try {
        const raw = JSON.parse(fs.readFileSync(WEBHOOKS_FILE, "utf8"));
        const list = Array.isArray(raw) ? raw : raw.webhooks;
        if (Array.isArray(list)) return list.filter((w) => w && typeof w.url === "string");
    } catch { /* faili haipo au siyo JSON — tunarudisha [] */ }
    return [];
}

function writeWebhooks(list) {
    fs.writeFileSync(WEBHOOKS_FILE, JSON.stringify({ webhooks: list }, null, 2) + "\n");
}

// --- Delivery ID (UUID v4) ---
function newDeliveryId() {
    return crypto.randomUUID();
}

// --- Saini: HMAC-SHA256 juu ya raw body ---
function signPayload(rawBody) {
    return "sha256=" + crypto.createHmac("sha256", WEBHOOK_SECRET).update(rawBody).digest("hex");
}

// --- Moja ya HTTP POST yenye timeout — inarudisha {ok, status} ---
function httpPostJson(urlString, headers, body) {
    return new Promise((resolve) => {
        let u;
        try {
            u = new URL(urlString);
        } catch {
            return resolve({ ok: false, status: 0, error: "invalid URL" });
        }
        if (u.protocol !== "http:" && u.protocol !== "https:") {
            return resolve({ ok: false, status: 0, error: "only http/https URLs are allowed" });
        }
        const isHttps = u.protocol === "https:";
        const mod = isHttps ? require("https") : http;
        const payload = Buffer.from(body, "utf8");
        const req = mod.request(
            {
                hostname: u.hostname,
                port: u.port || (isHttps ? 443 : 80),
                path: u.pathname + u.search,
                method: "POST",
                headers: { ...headers, "Content-Length": payload.length }
            },
            (res) => {
                res.resume();
                res.on("end", () => {
                    const ok = res.statusCode >= 200 && res.statusCode < 300;
                    resolve({ ok, status: res.statusCode });
                });
            }
        );
        req.setTimeout(WEBHOOK_TIMEOUT_MS, () => {
            req.destroy(new Error("timeout after " + WEBHOOK_TIMEOUT_MS + "ms"));
        });
        req.on("error", (err) => resolve({ ok: false, status: 0, error: err.message }));
        req.end(payload);
    });
}

// --- Retries (ndani ya process). Tunaanzisha kwenye boot pia. ---
const pendingRetries = new Set();
process.on("exit", () => { for (const t of pendingRetries) clearTimeout(t); });

async function deliverWithRetries(webhook, event, envelope, rawBody) {
    const headers = {
        "Content-Type": "application/json",
        "X-DAIRE-Event": event,
        "X-DAIRE-Delivery": envelope.delivery_id,
        "X-DAIRE-Signature": signPayload(rawBody),
        "User-Agent": "DAIRE-Middleware/1.0"
    };

    let last = await httpPostJson(webhook.url, headers, rawBody);
    for (let attempt = 1; !last.ok && attempt <= WEBHOOK_RETRY_DELAYS_MS.length; attempt++) {
        console.warn(
            `[Webhook] Delivery ${envelope.delivery_id} -> ${webhook.url} failed (HTTP ${last.status}${last.error ? " " + last.error : ""}); retry ${attempt}/${WEBHOOK_RETRY_DELAYS_MS.length} baada ya ${WEBHOOK_RETRY_DELAYS_MS[attempt - 1]}ms`
        );
        await new Promise((res) => {
            const t = setTimeout(() => {
                pendingRetries.delete(t);
                res();
            }, WEBHOOK_RETRY_DELAYS_MS[attempt - 1]);
            pendingRetries.add(t);
        });
        last = await httpPostJson(webhook.url, headers, rawBody);
    }

    if (last.ok) {
        console.log(`[Webhook] Delivered ${event} ${envelope.delivery_id} -> ${webhook.url} (HTTP ${last.status})`);
    } else {
        console.error(`[Webhook] FAILED permanently ${event} ${envelope.delivery_id} -> ${webhook.url}`);
        recordWebhookFailure(webhook, event, envelope, last);
    }
}

// --- Kumbukumbu ya shindikizo la mwisho (lender asiyepatikana) ---
function recordWebhookFailure(webhook, event, envelope, result) {
    try {
        let list = [];
        try {
            const raw = JSON.parse(fs.readFileSync(WEBHOOK_FAILURES_FILE, "utf8"));
            if (Array.isArray(raw)) list = raw;
        } catch { /* faili haipo bado */ }
        list.push({
            recordedAt: new Date().toISOString(),
            webhookId: webhook.id,
            url: webhook.url,
            lenderId: webhook.lenderId || null,
            event,
            deliveryId: envelope.delivery_id,
            httpStatus: result ? result.status : null,
            error: result ? result.error || null : null
        });
        if (list.length > 1000) list = list.slice(-1000);
        fs.writeFileSync(WEBHOOK_FAILURES_FILE, JSON.stringify(list, null, 2) + "\n");
    } catch (err) {
        console.warn("[Webhook] Shiop ya shindikizo haikuandikwa:", err.message);
    }
}

// --- Push kwa webhooks zote zilizosajili (au zilizo-chagua event hii) ---
function broadcast(event, payload) {
    const hooks = readWebhooks().filter(
        (w) => !Array.isArray(w.events) || w.events.length === 0 || w.events.includes(event)
    );
    if (hooks.length === 0) return;

    const envelope = {
        delivery_id: newDeliveryId(),
        event,
        channel: "blockchain_event",
        payload,
        broadcastAt: new Date().toISOString()
    };
    const rawBody = JSON.stringify(envelope);

    for (const hook of hooks) {
        deliverWithRetries(hook, event, envelope, rawBody).catch((err) => {
            console.error("[Webhook] Push loop error:", err.message);
        });
    }
}

// =====================================================================
// 2. BLOCKCHAIN PROVIDER & CONTRACT INITIALIZATION
// =====================================================================
function createProvider(rpcUrl) {
    if (!rpcUrl) throw new Error("RPC_URL is not set");
    if (rpcUrl.startsWith("ws")) return new ethers.WebSocketProvider(rpcUrl);
    return new ethers.JsonRpcProvider(rpcUrl);
}

async function bootCheck(provider, contractAddress) {
    // Jiulize maswali mawili kwa node: (1) upo? (2) contract ipo?
    let chainId;
    try {
        chainId = await provider.send("eth_chainId", []);
    } catch (err) {
        const isLocal = /127\.0\.0\.1|localhost/.test(process.env.RPC_URL || "");
        console.error("\n[Boot Failed] Cannot reach the RPC node at " + process.env.RPC_URL);
        console.error("  Reason: " + (err.shortMessage || err.message));
        if (isLocal) {
            console.error("\n  Local node haipo. Anza kwanza (terminal nyingine):\n");
            console.error("    npx hardhat node\n");
            console.error("  Kisha deploy:");
            console.error("    npm run deploy:local");
            console.error("  Kisha anza middleware tena:\n");
            console.error("    npm run start:local\n");
        } else {
            console.error("\n  Kagua RPC_URL (inyewe inafanya kazi, bila adhari za wizi).\n");
        }
        process.exit(1);
    }

    const code = await provider.getCode(contractAddress);
    if (code === "0x") {
        console.error("\n[Boot Failed] No contract code at " + contractAddress);
        console.error("  Contract haijawekwa kwenye chain hii (chainId " + chainId + ").");
        console.error("  Kama unatumia local node mpya, deploy tena:");
        console.error("    npm run deploy:local");
        console.error("  Kwa Sepolia, kagua CONTRACT_ADDRESS kwenye .env.sepolia.\n");
        process.exit(1);
    }

    console.log("[Boot OK] RPC " + process.env.RPC_URL + " (chainId " + chainId + ")");
    console.log("[Boot OK] DaireCreditScore at " + contractAddress);
    return { chainId };
}

const provider = createProvider(process.env.RPC_URL);
// NonceManager: inazuia "nonce too low" kwenye node ya local (automine) —
// inapanga mfululizo wa nonces ndani ya process hii.
const hubWallet = new ethers.NonceManager(
    new ethers.Wallet(process.env.HUB_PRIVATE_KEY, provider)
);
const daireContract = new ethers.Contract(process.env.CONTRACT_ADDRESS, DAIRE_ABI, hubWallet);

// Real-time listeners kupitia HTTP polling — inafanya local node na Sepolia.
// (Ilihifadhi kwenye kumbukumbu: WebSocket pekee ndiyo ilikuwa inataka wss.)
// Kila event inasukumwa pia kwa webhooks zilizosajili (section 1.5).
try {
    daireContract.on("ScoreCalculated", (borrowerRef, hub, score, band, version, assessedAt) => {
        console.log(`\n[EVENT: ScoreCalculated]`);
        console.log(`> BorrowerRef: ${borrowerRef}`);
        console.log(`> Score: ${score} | Band: ${RISK_BANDS[band]} | Version: ${version}`);
        broadcast("SCORE_CALCULATED", {
            borrowerRef,
            hub,
            calculation: "ON_CHAIN",
            score: Number(score),
            finalScore: Number(score),
            riskBand: RISK_BANDS[Number(band)],
            version: Number(version),
            assessedAt: Number(assessedAt)
        });
    });
    daireContract.on("ScoreRecorded", (borrowerRef, hub, finalScore, band, version, recordedAt) => {
        console.log(`\n[EVENT: ScoreRecorded]`);
        console.log(`> BorrowerRef: ${borrowerRef}`);
        console.log(`> FinalScore: ${finalScore} | Band: ${RISK_BANDS[band]} | Version: ${version}`);
        broadcast("SCORE_RECORDED", {
            borrowerRef,
            hub,
            calculation: "OFF_CHAIN",
            score: Number(finalScore),
            finalScore: Number(finalScore),
            riskBand: RISK_BANDS[Number(band)],
            version: Number(version),
            assessedAt: Number(recordedAt)
        });
    });
    daireContract.on("InsufficientEvidence", (borrowerRef, hub, missingMask) => {
        console.log(`\n[EVENT: InsufficientEvidence]`);
        console.log(`> BorrowerRef: ${borrowerRef} | Mask: ${missingMask}`);
        broadcast("INSUFFICIENT_EVIDENCE", {
            borrowerRef,
            hub,
            missingMask: Number(missingMask),
            missingExplanation: explainMissingMask(Number(missingMask))
        });
    });
} catch (listenerErr) {
    console.warn("[Listeners] Skipped:", listenerErr.message);
}

// (Kumbuka: real-time listeners ziko chini ya section 2 — HTTP polling,
//  inafanya kazi na local node NA Sepolia bila WebSocket API key.)

// =====================================================================
// 3. API ENDPOINTS (Web2 Central System Interaction)
// =====================================================================

/**
 * @route   POST /api/v1/score/submit
 * @notice  Phase 2 & 3: Submit aggregated features to blockchain for scoring
 */
app.post("/api/v1/score/submit", async (req, res) => {
    try {
        const { identityHash, salt, features } = req.body;

        if (!identityHash || !salt || !features) {
            return res.status(400).json({ success: false, error: "Missing required payload parameters" });
        }

        // Generate borrowerRef on-chain or locally via keccak256
        const borrowerRef = ethers.keccak256(ethers.toUtf8Bytes(`${identityHash}|${salt}`));

        console.log(`\n[Phase 2 Initiated] Submitting features for Ref: ${borrowerRef}`);

        // Broadcast Write Transaction to Blockchain (Consumes Gas)
        const txResponse = await daireContract.submitFeatures(borrowerRef, features);
        console.log(`[Phase 2 Success] Tx Broadcasted. Hash: ${txResponse.hash}`);

        // Phase 3: Wait for block confirmation
        const receipt = await txResponse.wait(1);

        if (receipt.status === 1) {
            // Read latest calculated score directly from contract view function
            const scoreData = await daireContract.getScore(borrowerRef);
            const dimensions = await daireContract.getDimensions(borrowerRef);

            // Handle Insufficient Evidence Gate Response
            if (scoreData.score === 0n && scoreData.band === 0n) {
                return res.status(422).json({
                    success: false,
                    status: "INSUFFICIENT_EVIDENCE",
                    borrowerRef,
                    message: "Data submitted failed the sufficiency gates (BR-10)."
                });
            }

            return res.status(200).json({
                success: true,
                status: "SCORED_SUCCESSFULLY",
                calculation: "ON_CHAIN",
                transactionHash: receipt.hash,
                blockNumber: receipt.blockNumber,
                data: {
                    borrowerRef,
                    score: Number(scoreData.score),
                    riskBand: RISK_BANDS[Number(scoreData.band)],
                    version: Number(scoreData.version),
                    assessedAt: Number(scoreData.assessedAt),
                    dimensions: {
                        d1_paymentReliability: Number(dimensions.d1),
                        d2_financialStability: Number(dimensions.d2),
                        d3_debtManagement: Number(dimensions.d3),
                        d4_behaviouralConsistency: Number(dimensions.d4),
                        d5_trustEvidence: Number(dimensions.d5)
                    }
                }
            });
        } else {
            return res.status(500).json({ success: false, error: "Transaction reverted on EVM level." });
        }

    } catch (error) {
        console.error("[Submission Error]:", error);
        return res.status(500).json({
            success: false,
            error: error.reason || error.message || "EVM Execution Error"
        });
    }
});

/**
 * @route   POST /api/v1/score/submit-calculated
 * @notice  NJIA YA PILI — score inahesabiwa HAPA (scoreEngine.js), kisha
 *          contract inapokea SINGLE VALUE (finalScore) + dimensions tano tu.
 *          Inafaa kwa web app: payload ni ndogo, hesabu haigharimi gas.
 *
 *          Inakubala aina mbili za input:
 *          1. { identityHash, salt, features }    -> engine inahesabu dims + score
 *          2. { identityHash, salt, dimensions }  -> dims zimeshahesabiwa (d1..d5)
 */
app.post("/api/v1/score/submit-calculated", async (req, res) => {
    try {
        const { identityHash, salt, features, dimensions } = req.body;

        if (!identityHash || !salt) {
            return res.status(400).json({
                success: false,
                error: "Missing identityHash or salt"
            });
        }
        if (!features && !dimensions) {
            return res.status(400).json({
                success: false,
                error: "Provide either 'features' (raw derived numbers) or 'dimensions' (d1..d5)"
            });
        }

        // 1. Generate Borrower Reference Hash (sawa na makeBorrowerRef ya contract)
        const borrowerRef = ethers.keccak256(
            ethers.toUtf8Bytes(`${identityHash}|${salt}`)
        );

        console.log(`\n[Phase 2 (off-chain calc)] Ref: ${borrowerRef}`);

        // 2. Compute dimensions + SINGLE SCORE kwa Off-Chain Matrix Engine
        let dims, finalScore, band, missingMask = 0;
        if (features) {
            const result = evaluateOffChain(features);
            if (!result.ok) {
                return res.status(422).json({
                    success: false,
                    status: "INSUFFICIENT_EVIDENCE",
                    borrowerRef,
                    missingMask: result.missingMask,
                    message: result.reason
                });
            }
            dims = result.dimensions;
            finalScore = result.finalScore;
            band = result.band;
        } else {
            dims = {
                d1: Number(dimensions.d1),
                d2: Number(dimensions.d2),
                d3: Number(dimensions.d3),
                d4: Number(dimensions.d4),
                d5: Number(dimensions.d5)
            };
            finalScore = calculateCreditScore(dims);
            band = bandOfScore(finalScore, Math.min(dims.d1, dims.d2, dims.d3, dims.d4, dims.d5));
        }

        // 3. Submit SINGLE transaction: (borrowerRef, finalScore, d1..d5)
        const txResponse = await daireContract.submitCalculatedScore(
            borrowerRef, finalScore, dims.d1, dims.d2, dims.d3, dims.d4, dims.d5
        );
        console.log(`[Tx Broadcasted] Hash: ${txResponse.hash}`);

        // 4. Wait for block confirmation na chukua version kutoka kwenye event
        const receipt = await txResponse.wait(1);
        if (receipt.status !== 1) {
            return res.status(500).json({ success: false, error: "Transaction reverted on EVM level." });
        }

        let version = 1;
        for (const log of receipt.logs) {
            try {
                const parsed = daireContract.interface.parseLog({ topics: [...log.topics], data: log.data });
                if (parsed && parsed.name === "ScoreRecorded") {
                    version = Number(parsed.args.version);
                }
            } catch { /* log siyo ya ABI hii — ruka */ }
        }

        return res.status(200).json({
            success: true,
            status: "SCORE_RECORDED",
            calculation: "OFF_CHAIN",
            transactionHash: receipt.hash,
            blockNumber: receipt.blockNumber,
            data: {
                borrowerRef,
                finalScore,
                riskBand: band,
                dimensions: dimensionLabels(dims),
                version
            }
        });
    } catch (error) {
        console.error("[Calculated Submission Error]:", error);
        return res.status(500).json({
            success: false,
            error: error.reason || error.message || "EVM Execution Error"
        });
    }
});

/**
 * @route   POST /api/v1/score/preview
 * @notice  KAGUA BILA KULIPA — hesabu ileile ya njia ya pili (off-chain)
 *          lakini HAKUNA transaction, HAKUNA gas, HAKUNA kuandika chain.
 *          Inakubala input zote mbili: `features` (raw) au `dimensions` (d1..d5).
 *          Ndiyo rika la `previewScore` ya contract — parity inathibitishwa.
 */
app.post("/api/v1/score/preview", async (req, res) => {
    try {
        const { identityHash, salt, features, dimensions } = req.body;

        if (!features && !dimensions) {
            return res.status(400).json({
                success: false,
                error: "Provide either 'features' (raw derived numbers) or 'dimensions' (d1..d5)"
            });
        }

        // borrowerRef inahesabiwa tu kama identity ilipeanwa — preview haiitaji
        const borrowerRef =
            identityHash && salt
                ? ethers.keccak256(ethers.toUtf8Bytes(`${identityHash}|${salt}`))
                : null;

        if (features) {
            const result = evaluateOffChain(features);
            if (!result.ok) {
                return res.status(422).json({
                    success: true,
                    status: "INSUFFICIENT_EVIDENCE",
                    calculation: "OFF_CHAIN",
                    preview: true,
                    borrowerRef,
                    missingMask: result.missingMask,
                    missingExplanation: explainMissingMask(result.missingMask),
                    message: result.reason
                });
            }
            return res.status(200).json({
                success: true,
                status: "PREVIEW",
                calculation: "OFF_CHAIN",
                preview: true,
                borrowerRef,
                data: {
                    finalScore: result.finalScore,
                    riskBand: result.band,
                    dimensions: dimensionLabels(result.dimensions)
                }
            });
        }

        // dimensions mode — d1..d5 zimekwishahesabiwa na mteja
        const dims = {
            d1: Number(dimensions.d1),
            d2: Number(dimensions.d2),
            d3: Number(dimensions.d3),
            d4: Number(dimensions.d4),
            d5: Number(dimensions.d5)
        };
        for (const k of ["d1", "d2", "d3", "d4", "d5"]) {
            if (!Number.isFinite(dims[k]) || dims[k] < 0 || dims[k] > 100) {
                return res.status(400).json({
                    success: false,
                    error: `dimensions.${k} must be a number between 0 and 100`
                });
            }
        }

        const finalScore = calculateCreditScore(dims);
        const band = bandOfScore(finalScore, Math.min(dims.d1, dims.d2, dims.d3, dims.d4, dims.d5));

        return res.status(200).json({
            success: true,
            status: "PREVIEW",
            calculation: "OFF_CHAIN",
            preview: true,
            borrowerRef,
            data: {
                finalScore,
                riskBand: band,
                dimensions: dimensionLabels(dims)
            }
        });
    } catch (error) {
        console.error("[Preview Error]:", error);
        return res.status(500).json({
            success: false,
            error: error.message || "Preview calculation failed"
        });
    }
});

/**
 * @route   GET /api/v1/score/:borrowerRef
 * @notice  Phase 4: Synchronous read call (Zero Gas) to fetch score & dimensions
 */
app.get("/api/v1/score/:borrowerRef", async (req, res) => {
    try {
        const { borrowerRef } = req.params;

        const scoreData = await daireContract.getScore(borrowerRef);
        const dimensions = await daireContract.getDimensions(borrowerRef);

        if (!scoreData.exists) {
            return res.status(404).json({ success: false, message: "No credit assessment found for this reference" });
        }

        return res.status(200).json({
            success: true,
            data: {
                borrowerRef,
                score: Number(scoreData.score),
                riskBand: RISK_BANDS[Number(scoreData.band)],
                version: Number(scoreData.version),
                assessedAt: Number(scoreData.assessedAt),
                dimensions: {
                    d1: Number(dimensions.d1),
                    d2: Number(dimensions.d2),
                    d3: Number(dimensions.d3),
                    d4: Number(dimensions.d4),
                    d5: Number(dimensions.d5)
                }
            }
        });
    } catch (error) {
        return res.status(500).json({ success: false, error: error.message });
    }
});

// =====================================================================
// 3.5 WEBHOOK MANAGEMENT ENDPOINTS — usajili wa lenders wanaopushwa
// =====================================================================

/**
 * @route   POST /api/v1/webhooks
 * @notice  Sajili URL ya lender itakayopushiwa matokeo ya contract.
 *          Body: { "url": "http://...", "lenderId": "LDR-DEMO-FLOW",
 *                  "events": ["SCORE_CALCULATED", "SCORE_RECORDED", "INSUFFICIENT_EVIDENCE"] }
 *          `events` ni siyo lazima — [] au kukosekana = events zote.
 */
app.post("/api/v1/webhooks", (req, res) => {
    const { url, lenderId, events } = req.body || {};

    if (!url || typeof url !== "string") {
        return res.status(400).json({ success: false, error: "url (string) is required" });
    }
    let parsed;
    try {
        parsed = new URL(url);
    } catch {
        return res.status(400).json({ success: false, error: "url is not a valid absolute URL" });
    }
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        return res.status(400).json({ success: false, error: "only http/https URLs are allowed" });
    }

    if (events !== undefined) {
        if (!Array.isArray(events) || events.some((e) => !WEBHOOK_EVENTS.includes(e))) {
            return res.status(400).json({
                success: false,
                error: "events must be a subset of " + WEBHOOK_EVENTS.join(", ")
            });
        }
    }

    const hooks = readWebhooks();
    const webhook = {
        id: "wh_" + crypto.randomBytes(8).toString("hex"),
        url,
        lenderId: lenderId || null,
        events: Array.isArray(events) ? events : [],
        createdAt: new Date().toISOString()
    };
    hooks.push(webhook);
    writeWebhooks(hooks);

    console.log(`[Webhooks] Registered ${webhook.id} -> ${url} (lender: ${webhook.lenderId || "n/a"})`);
    return res.status(201).json({
        success: true,
        webhook,
        secretHint: "HMAC secret: WEBHOOK_SECRET env au webhooks.secret.json (X-DAIRE-Signature: sha256=<hex>)"
    });
});

/**
 * @route   GET /api/v1/webhooks
 * @notice  Orodha ya webhooks zilizosajili
 */
app.get("/api/v1/webhooks", (req, res) => {
    return res.status(200).json({ success: true, webhooks: readWebhooks() });
});

/**
 * @route   DELETE /api/v1/webhooks/:id
 * @notice  Ondoa usajili
 */
app.delete("/api/v1/webhooks/:id", (req, res) => {
    const hooks = readWebhooks();
    const idx = hooks.findIndex((w) => w.id === req.params.id);
    if (idx === -1) {
        return res.status(404).json({ success: false, error: "webhook id not found" });
    }
    const [removed] = hooks.splice(idx, 1);
    writeWebhooks(hooks);
    console.log(`[Webhooks] Removed ${removed.id} -> ${removed.url}`);
    return res.status(200).json({ success: true, removed: removed.id });
});

/**
 * @route   POST /api/v1/webhooks/:id/test
 * @notice  Tuma test ping kwa webhook moja — inathibitisha URL na saini
 */
app.post("/api/v1/webhooks/:id/test", async (req, res) => {
    const hook = readWebhooks().find((w) => w.id === req.params.id);
    if (!hook) {
        return res.status(404).json({ success: false, error: "webhook id not found" });
    }
    const envelope = {
        delivery_id: newDeliveryId(),
        event: "TEST_PING",
        channel: "blockchain_event",
        payload: {
            message: "DAIRE webhook test — kama unapokea hii, usajili wako unafanya kazi.",
            contractAddress: process.env.CONTRACT_ADDRESS,
            testBody: req.body || null
        },
        broadcastAt: new Date().toISOString()
    };
    const rawBody = JSON.stringify(envelope);
    const result = await httpPostJson(hook.url, {
        "Content-Type": "application/json",
        "X-DAIRE-Event": "TEST_PING",
        "X-DAIRE-Delivery": envelope.delivery_id,
        "X-DAIRE-Signature": signPayload(rawBody),
        "User-Agent": "DAIRE-Middleware/1.0"
    }, rawBody);

    return res.status(result.ok ? 200 : 502).json({
        success: result.ok,
        deliveryId: envelope.delivery_id,
        httpStatus: result.status,
        error: result.error || null
    });
});

// Start Server — boot check kwanza (RPC + contract code), kisha sikiliza
const PORT = process.env.PORT || 5000;

bootCheck(provider, process.env.CONTRACT_ADDRESS)
    .then(({ chainId }) => {
        app.listen(PORT, () => {
            console.log(`DAIRE Middleware Service running on port ${PORT}`);
            console.log("[OK] Endpoints:");
            console.log("  POST /api/v1/score/submit             (njia ya 1 — contract inahesabu)");
            console.log("  POST /api/v1/score/submit-calculated  (njia ya pili — engine inahesabu)");
            console.log("  POST /api/v1/score/preview            (kagua BILA gas — hakuna kuandika chain)");
            console.log("  GET  /api/v1/score/:borrowerRef");
            console.log("[OK] Webhooks:");
            console.log("  POST /api/v1/webhooks                 (sajili lender URL)");
            console.log("  GET  /api/v1/webhooks                 (orodha)");
            console.log("  DELETE /api/v1/webhooks/:id           (ondoa)");
            console.log("  POST /api/v1/webhooks/:id/test        (tuma test ping)");
            const hooks = readWebhooks();
            console.log(`[OK] Registered webhooks: ${hooks.length} | chainId ${chainId}`);
        });
    })
    .catch((err) => {
        console.error("[Boot Failed]", err.shortMessage || err.message);
        process.exit(1);
    });
