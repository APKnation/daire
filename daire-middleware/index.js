const path = require("path");
const fs = require("fs");
const express = require("express");
const { ethers } = require("ethers");
const {
    evaluateOffChain,
    calculateCreditScore
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
            console.error("  Kisha anza middleware tena:");
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
try {
    daireContract.on("ScoreCalculated", (borrowerRef, hub, score, band, version) => {
        console.log(`\n[EVENT: ScoreCalculated]`);
        console.log(`> BorrowerRef: ${borrowerRef}`);
        console.log(`> Score: ${score} | Band: ${RISK_BANDS[band]} | Version: ${version}`);
    });
    daireContract.on("ScoreRecorded", (borrowerRef, hub, finalScore, band, version) => {
        console.log(`\n[EVENT: ScoreRecorded]`);
        console.log(`> BorrowerRef: ${borrowerRef}`);
        console.log(`> FinalScore: ${finalScore} | Band: ${RISK_BANDS[band]} | Version: ${version}`);
    });
    daireContract.on("InsufficientEvidence", (borrowerRef, hub, missingMask) => {
        console.log(`\n[EVENT: InsufficientEvidence]`);
        console.log(`> BorrowerRef: ${borrowerRef} | Mask: ${missingMask}`);
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
                dimensions: {
                    d1_paymentReliability: dims.d1,
                    d2_financialStability: dims.d2,
                    d3_debtManagement: dims.d3,
                    d4_behaviouralConsistency: dims.d4,
                    d5_trustEvidence: dims.d5
                },
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

// Start Server — boot check kwanza (RPC + contract code), kisha sikiliza
const PORT = process.env.PORT || 5000;

bootCheck(provider, process.env.CONTRACT_ADDRESS)
    .then(() => {
        app.listen(PORT, () => {
            console.log(`DAIRE Middleware Service running on port ${PORT}`);
            console.log("[OK] Endpoints:");
            console.log("  POST /api/v1/score/submit             (njia ya 1 — contract inahesabu)");
            console.log("  POST /api/v1/score/submit-calculated  (njia ya pili — engine inahesabu)");
            console.log("  GET  /api/v1/score/:borrowerRef");
        });
    })
    .catch((err) => {
        console.error("[Boot Failed]", err.shortMessage || err.message);
        process.exit(1);
    });