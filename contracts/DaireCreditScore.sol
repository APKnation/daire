// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title  DaireCreditScore
 * @notice STEP 2 — hesabu ya credit score INDANI ya smart contract.
 *
 *         Contract hii inapokea namba zilizokokotolewa na Credit Information Hub
 *         (Central System), inahesabu dimensions tano (D1..D5), inatoa score ya
 *         300-850, inaihifadhi kwenye ledger, na inaitoa kupitia read functions
 *         ambazo API yetu itaziita.
 *
 *         KENGELE MPUYA (2026): mkopaji asiye na tukio lolote baya hupata
 *         bonus ya kila mwaka uliopita — hii inathibitisha "stability"
 *         kwa mkopaji ambaye historia yake ni safi lakini mifumo ya kawaida
 *         haioneshi chochote juu yake.
 *
 *         HAKUNA AI HAPA. Ni hesabu za kawaida tu, zenye uzito uliochapishwa.
 *         Mtu yeyote anaweza kusoma code hii na kuthibitisha kwamba score ni
 *         sahihi. Hii ndiyo tofauti yetu na Spectral, Cred Protocol na wengine
 *         wanaohesabu nje ya chain.
 *
 * @dev    KANUNI YA DHAHABU: hakuna data binafsi inayoingia hapa.
 *
 *         Hakuna jina. Hakuna kitambulisho. Hakuna kiasi cha mkopo. Hakuna
 *         tarehe. Namba zilizokokotolewa TU, zikiwa zimeunganishwa na
 *         `borrowerRef` ambayo ni keccak256 hash. Kila kitu kwenye blockchain
 *         ni cha umma milele — kwa hivyo tunaweka kile kisichoweza kumtambulisha
 *         mtu.
 *
 *         BASIS POINTS: Solidity haina desimali. Hakuna `float`. Asilimia
 *         zinawakilishwa kwa basis points: 9750 = 97.50%, 10000 = 100.00%.
 *         Kanuni ya kukumbuka: GAWANYA MWISHO KABISA. `(a * b) / c` inahifadhi
 *         usahihi ambao `(a / c) * b` inaupoteza.
 *
 *         SCALING YA 300-850 (min-max transformation):
 *             S = 300 + (weightedSum x 550) / 10000
 *         ambapo weightedSum = (D1 x 30 + D2 x 20 + D3 x 15 + D4 x 20 + D5 x 15)
 *         na thamani yake ya juu kabisa ni 100 x 100 = 10,000.
 *         Fomula hii inafuata mbinu ya min-max normalization iliyoelezwa kwenye
 *         arXiv:2412.00710v2. Mkopaji mbovu kabisa anapata 300, mbora kabisa
 *         anapata 850 — kama FICO na VantageScore vyote vinavyofanya.
 */
contract DaireCreditScore {

    // =====================================================================
    // SEHEMU 1 — CONSTANTS
    // Kila kanuni ya scoring imewekwa hapa kama constant ya `public`, ili
    // mtu yeyote aweze kuisoma kutoka Etherscan bila kusoma code.
    // =====================================================================

    string public constant SYSTEM = "DAIRE - Decentralized AI Reputation Engine";
    string public constant RULESET_VERSION = "DAIRE-RULES-2.0-US-RANGE";
    string public constant DOC_REF = "DAIRE/RES/003 Ch.6";

    /// @notice Mpangilio wa score ni sawa na wa Marekani (FICO na VantageScore
    ///         vyote vinatumia 300-850). Uzito ndio uliobadilishwa kwa ajili ya
    ///         Tanzania — siyo mazingira ya kawaida ya Marekani.
    uint16 public constant MIN_SCORE = 300;
    uint16 public constant MAX_SCORE = 850;
    uint16 public constant BPS = 10000;              // 100.00%
    uint16 public constant NEVER = type(uint16).max; // hakuna tukio baya kamwe

    // --- Uzito wa dimensions (Tanzania-adjusted). Jumla lazima iwe 100. ---
    // Reference: FICO 35/30/15/10/10, VantageScore 4.0 41/20/20/11/6+2.
    // Sisi tunapunguza "Amounts Owed" (D3) na kuongeza "Financial Stability"
    // (D2) kwa sababu Tanzania kuna wateja wengi wasio na mkopo wa benki,
    // lakini wana miamala ya mobile money inayothibitisha uthabiti wa fedha.
    uint8 public constant W_D1 = 30;  // Payment Reliability      (FICO: 35%)
    uint8 public constant W_D2 = 20;  // Financial Stability      (FICO: 0% — UltraFICO insight)
    uint8 public constant W_D3 = 15;  // Credit & Debt Management (FICO: 30%)
    uint8 public constant W_D4 = 20;  // Behavioural Consistency  (FICO: ~15% length+trends)
    uint8 public constant W_D5 = 15;  // Verified Trust Evidence  (hakuna mfano — DAIRE)

    // --- Gates za utoshelevu wa ushahidi (BR-10). Hazina njia ya kukwepwa. ---
    uint16 public constant MIN_HISTORY_MONTHS   = 6;
    uint16 public constant MIN_BEHAVIOUR_EVENTS = 8;
    uint16 public constant MIN_REPAYMENT_RECORDS = 1;
    uint8  public constant MIN_VERIFIED_SOURCES = 1;

    // --- Bits za `missingMask`, zinaeleza ni gate ipi imeshindwa ---
    uint8 public constant MISSING_HISTORY    = 1; // 0001
    uint8 public constant MISSING_EVENTS     = 2; // 0010
    uint8 public constant MISSING_REPAYMENTS = 4; // 0100
    uint8 public constant MISSING_VERIFIED   = 8; // 1000

    // --- Kiwango cha chini cha dimension kinachozuia band nzuri ---
    uint8 public constant DIMENSION_FLOOR = 40;

    // =====================================================================
    // SEHEMU 2 — AINA ZA DATA
    // =====================================================================

    enum RiskBand {
        NONE,        // 0 — hakuna assessment (ushahidi hautoshi)
        POOR,        // 1 — score 300-579
        FAIR,        // 2 — score 580-669
        GOOD,        // 3 — score 670-739
        VERY_GOOD,   // 4 — score 740-799
        EXCEPTIONAL  // 5 — score 800-850
    }

    /**
     * @notice Namba zinazotumwa na Credit Information Hub.
     * @dev    Mpangilio wa fields ni MUHIMU — ndivyo utakavyoziingiza kwenye
     *         Remix kama tuple. Usibadilishe mpangilio bila kusasisha docs.
     */
    struct Features {
        // --- Gates (zinakaguliwa kabla ya hesabu yoyote) ---
        uint16 historyMonths;          // 1. miezi ya historia inayoonekana
        uint16 behaviourEventCount;    // 2. jumla ya matukio ya kitabia
        uint16 repaymentRecordCount;   // 3. rekodi za marejesho au miamala
        uint8  verifiedSourceCount;    // 4. vyanzo vyenye status VERIFIED

        // --- D1: Payment Reliability ---
        uint16 onTimeRatioBps;         // 5. uwiano wa kulipa kwa wakati (bps)
        uint16 maxDaysLate;            // 6. siku nyingi zaidi za kuchelewa
        uint16 missedCount;            // 7. marejesho yaliyokosekana kabisa
        uint16 onTimeStreak;           // 8. mfululizo wa sasa wa kulipa kwa wakati

        // --- D2: Financial Stability ---
        uint16 activeMonthsBps;        // 9.  miezi yenye muamala angalau 1 (bps)
        uint16 regularMonthsBps;       // 10. miezi yenye miamala 4+ (bps)
        uint16 balanceStabilityBps;    // 11. uthabiti wa salio (bps, juu = thabiti)

        // --- D3: Credit and Debt Management ---
        uint16 defaultCount;           // 12. mikopo iliyoingia default (miezi 36)
        uint16 completedCount;         // 13. mikopo iliyokamilika
        uint16 utilizationBps;         // 14. matumizi ya mkopo (bps)
        uint8  activeLenderCount;      // 15. taasisi zenye mkopo hai

        // --- D4: Behavioural Consistency ---
        int16  trendBps;               // 16. mwelekeo: chanya = inaimarika
        uint16 volatilityBps;          // 17. kuyumba kwa tabia (juu = mbaya)
        uint16 monthsSinceAdverse;     // 18. miezi tangu tukio baya; NEVER = hakuna

        // --- D5: Verified Trust Evidence ---
        uint8  distinctSourceCount;    // 19. vyanzo huru vyote
        uint16 meanCorroborationX100;  // 20. wastani wa uthibitisho x100 (250 = 2.50)
        uint8  openConflictCount;      // 21. migongano ambayo haijatatuliwa
    }

    /// @notice Matokeo yaliyohifadhiwa kwenye ledger.
    struct Assessment {
        uint16  score;        // 300-850
        uint8   d1;
        uint8   d2;
        uint8   d3;
        uint8   d4;
        uint8   d5;
        RiskBand band;
        uint32  assessedAt;   // block.timestamp
        uint32  version;      // toleo la assessment kwa mkopaji huyu
        address submittedBy;  // Hub iliyotuma
    }

    // =====================================================================
    // SEHEMU 3 — STORAGE
    // =====================================================================

    address public owner;

    /// @notice Hub zinazoruhusiwa kutuma features. Bila hii, mtu yeyote
    ///         angeweza kutuma namba za uongo na kujipatia score nzuri.
    mapping(address => bool) public authorizedHubs;

    /// @notice Assessment ya sasa kwa kila mkopaji.
    mapping(bytes32 => Assessment) private _current;

    /// @notice Historia kamili. Hatufuti wala kubadilisha — tunaongeza tu.
    mapping(bytes32 => Assessment[]) private _history;

    /// @notice Idadi ya assessments zote zilizotolewa na contract hii.
    uint256 public totalAssessments;

    /// @notice Idadi ya maombi yaliyokataliwa kwa ukosefu wa ushahidi.
    uint256 public totalInsufficient;

    /// @notice Ikiwa `true`, band ya rekodi za `submitCalculatedScore`
    ///         inatokana na score iliyowasilishwa. Ikiwa `false` (default),
    ///         band inabaki NONE kwenye rekodi hizo — ledger inahifadhi
    ///         namba tu, bila tathmini ya upya iliyotolewa nje ya chain.
    bool public useSubmittedBand;

    // =====================================================================
    // SEHEMU 4 — EVENTS
    // Hapa ndipo API yetu itasikiliza.
    // =====================================================================

    event HubAuthorized(address indexed hub, bool allowed);
    event OwnerTransferred(address indexed from, address indexed to);

    event ScoreCalculated(
        bytes32 indexed borrowerRef,
        address indexed hub,
        uint16  score,
        RiskBand band,
        uint32  version,
        uint32  assessedAt
    );

    event DimensionsRecorded(
        bytes32 indexed borrowerRef,
        uint32  version,
        uint8   d1,
        uint8   d2,
        uint8   d3,
        uint8   d4,
        uint8   d5
    );

    event InsufficientEvidence(
        bytes32 indexed borrowerRef,
        address indexed hub,
        uint8   missingMask
    );

    /// @notice Tukio la njia ya pili: score iliyohesabiwa NJE ya chain.
    event ScoreRecorded(
        bytes32 indexed borrowerRef,
        address indexed hub,
        uint16  finalScore,
        RiskBand band,
        uint32  version,
        uint32  recordedAt
    );

    event UseSubmittedBandToggled(bool enabled);

    // =====================================================================
    // SEHEMU 5 — ACCESS CONTROL
    // =====================================================================

    modifier onlyOwner() {
        require(msg.sender == owner, "DAIRE: si owner");
        _;
    }

    modifier onlyHub() {
        require(authorizedHubs[msg.sender], "DAIRE: Hub haijaruhusiwa");
        _;
    }

    constructor() {
        owner = msg.sender;
        // Anayeweka contract anakuwa Hub ya kwanza, ili uweze kujaribu mara moja.
        authorizedHubs[msg.sender] = true;
        emit OwnerTransferred(address(0), msg.sender);
        emit HubAuthorized(msg.sender, true);
    }

    function setHub(address hub, bool allowed) external onlyOwner {
        require(hub != address(0), "DAIRE: anwani batili");
        authorizedHubs[hub] = allowed;
        emit HubAuthorized(hub, allowed);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "DAIRE: anwani batili");
        emit OwnerTransferred(owner, newOwner);
        owner = newOwner;
    }

    /**
     * @notice Zima au washa tathmini ya band kwa score zilizohesabiwa nje ya
     *         chain. Chaguo la config tu — kanuni za hesabu za njia ya kwanza
     *         zimekaa kweli zimekwama (immutable).
     */
    function setUseSubmittedBand(bool enabled) external onlyOwner {
        useSubmittedBand = enabled;
        emit UseSubmittedBandToggled(enabled);
    }

    // =====================================================================
    // SEHEMU 6 — HESABU (pure functions — hazibadilishi chochote)
    //
    // Zote ni `pure`: zinachukua namba, zinarudisha namba. Hazisomi wala
    // kuandika storage. Hii inamaanisha unaweza kuzijaribu bila gas yoyote.
    // =====================================================================

    /// @dev Kizuizi cha thamani ndani ya mipaka. Tunatumia int256 ndani ili
    ///      kuepuka underflow ya uint wakati wa kutoa pointi.
    function _clamp(int256 v, int256 lo, int256 hi) private pure returns (uint8) {
        if (v < lo) v = lo;
        if (v > hi) v = hi;
        return uint8(uint256(v));
    }

    /**
     * @notice D1 — Payment Reliability. Uzito 30%, mkubwa kuliko wote.
     * @dev    Uzito huu unalingana na FICO (35%) na OCCR (35%), na na
     *         VantageScore inayoiita "extremely influential". Tumepunguza
     *         kidogo kwa sababu Tanzania tuna vyanzo vingine vya ushahidi
     *         ambavyo Marekani haina (mobile money, D2 na D5).
     */
    function scoreD1(Features calldata f) public pure returns (uint8) {
        int256 pts;

        // Msingi: uwiano wa kulipa kwa wakati
        if      (f.onTimeRatioBps >= 9800) pts = 100;
        else if (f.onTimeRatioBps >= 9500) pts = 85;
        else if (f.onTimeRatioBps >= 9000) pts = 70;
        else if (f.onTimeRatioBps >= 8000) pts = 50;
        else if (f.onTimeRatioBps >= 6000) pts = 28;
        else                               pts = 10;

        // Ukali wa ucheleweshaji: -2 kwa kila siku 10, kikomo -20
        int256 severity = (int256(uint256(f.maxDaysLate)) / 10) * 2;
        if (severity > 20) severity = 20;
        pts -= severity;

        // Marejesho yaliyokosekana: -6 kila moja, kikomo -30
        int256 missed = int256(uint256(f.missedCount)) * 6;
        if (missed > 30) missed = 30;
        pts -= missed;

        // Mfululizo mzuri wa miezi 12+: +5
        if (f.onTimeStreak >= 12) pts += 5;

        return _clamp(pts, 0, 100);
    }

    /**
     * @notice D2 — Financial Stability. Uzito 20%.
     * @dev    Hii ndiyo dimension inayomwezesha mkopaji asiye na historia ya
     *         mikopo kupimwa. Ni vipimo vilevile vinne ambavyo UltraFICO
     *         iliongeza ilipohitaji kupima watu wasio na credit file.
     *         Uzito umeongezwa 15% -> 20% kwa sababu Tanzania mzunguko wa
     *         mobile money ndiyo uthibitisho mkuu wa uwezo wa kulipa.
     */
    function scoreD2(Features calldata f) public pure returns (uint8) {
        uint256 continuity = (40 * uint256(f.activeMonthsBps)) / BPS;
        uint256 regularity = (30 * uint256(f.regularMonthsBps)) / BPS;
        uint256 stability  = (30 * uint256(f.balanceStabilityBps)) / BPS;
        return _clamp(int256(continuity + regularity + stability), 0, 100);
    }

    /**
     * @notice D3 — Credit and Debt Management. Uzito 15%.
     * @dev    Angalia utilization: 30%-70% ni eneo zuri, siyo adhabu.
     *         Tumechukua wazo hili kutoka ARCx, ambayo rewards curve yake
     *         inafika kilele kwenye 60% ya matumizi. Mtu asiyetumia mkopo
     *         kabisa hapaswi kushinda mtu anayeutumia vizuri.
     *         Uzito umepungua 25% -> 15% kwa sababu watanzania wengi hawana
     *         mkopo wa benki (FICO inaupa 30% kwa "Amounts Owed").
     */
    function scoreD3(Features calldata f) public pure returns (uint8) {
        int256 pts = 100;

        // Default: -35 kila moja, kikomo -70
        int256 defaults = int256(uint256(f.defaultCount)) * 35;
        if (defaults > 70) defaults = 70;
        pts -= defaults;

        // Mikopo iliyokamilika: +10 kila moja, kikomo +20
        int256 completed = int256(uint256(f.completedCount)) * 10;
        if (completed > 20) completed = 20;
        pts += completed;

        // Matumizi ya mkopo
        if      (f.utilizationBps >  9000) pts -= 25;
        else if (f.utilizationBps >  7000) pts -= 15;
        else if (f.utilizationBps >= 3000) pts -= 0;   // eneo zuri
        else                               pts += 5;

        // Kukopa taasisi nyingi kwa wakati mmoja
        if      (f.activeLenderCount >= 4) pts -= 20;
        else if (f.activeLenderCount == 3) pts -= 10;

        return _clamp(pts, 0, 100);
    }

    /**
     * @dev Adhabu ya tukio baya inayopungua kadri linavyozeeka.
     *      Fomula: 40 x 0.5 ^ (miezi / 12)
     *
     *      Leo        -> 40 pointi
     *      Mwaka 1    -> 20
     *      Miaka 2    -> 10
     *      Miaka 3    ->  5
     *      Miaka 4    ->  2
     *      Miaka 6+   ->  0
     *
     *      Tunatumia interpolation ya mstari kati ya kila mwaka ili adhabu
     *      ipungue taratibu badala ya kuruka ghafla kila Januari.
     */
    function adversePenalty(uint16 monthsSince) public pure returns (uint256) {
        if (monthsSince == NEVER) return 0;
        uint256 h = uint256(monthsSince) / 12;
        if (h >= 6) return 0;
        uint256 hi = uint256(40) >> h;        // thamani mwanzoni mwa mwaka h
        uint256 lo = uint256(40) >> (h + 1);  // thamani mwanzoni mwa mwaka h+1
        uint256 r  = uint256(monthsSince) % 12;
        return hi - ((hi - lo) * r) / 12;
    }

    /**
     * @notice D4 — Behavioural Consistency. Uzito 20%.
     * @dev    Hii ndiyo inayopima MWELEKEO, siyo hali ya sasa tu. Ni wazo
     *         lilelile ambalo sekta inaliita "trended attributes".
     *         Uzito umeongezwa 15% -> 20% kwa sababu nidhamu ya miamala ya
     *         kila siku ni ishara ya kwanza ya hatari kwenye mazingira ya
     *         Tanzania, kabla ya rekodi ya mikopo kuwepo.
     */
    function scoreD4(Features calldata f) public pure returns (uint8) {
        int256 pts = 60;

        // Mwelekeo: +/- 30 pointi kulingana na trendBps
        pts += (int256(f.trendBps) * 30) / int256(uint256(BPS));

        // Kuyumba: hadi -20
        pts -= int256((20 * uint256(f.volatilityBps)) / BPS);

        // Ukaribu wa tukio baya la mwisho
        pts -= int256(adversePenalty(f.monthsSinceAdverse));

        return _clamp(pts, 0, 100);
    }

    /**
     * @notice D5 — Verified Trust Evidence. Uzito 15%.
     * @dev    Dimension hii haina mfano kwenye mfumo wowote wa dunia
     *         tuliochunguza. Inapima ni kiasi gani mfumo unastahili kuamini
     *         dimensions nyingine nne.
     */
    function scoreD5(Features calldata f) public pure returns (uint8) {
        // Urefu wa historia: hadi 35, ikifika kilele miezi 36
        uint256 months = uint256(f.historyMonths);
        if (months > 36) months = 36;
        uint256 span = (35 * months) / 36;

        // Uwiano wa vyanzo vilivyothibitishwa: hadi 30
        uint256 verif = 0;
        if (f.distinctSourceCount > 0) {
            uint256 v = uint256(f.verifiedSourceCount);
            uint256 d = uint256(f.distinctSourceCount);
            if (v > d) v = d;
            verif = (30 * v) / d;
        }

        // Upana wa vyanzo: hadi 25
        uint256 breadth;
        if      (f.distinctSourceCount >= 3) breadth = 25;
        else if (f.distinctSourceCount == 2) breadth = 20;
        else if (f.distinctSourceCount == 1) breadth = 10;

        // Uthibitisho wa vyanzo huru: hadi 10, ukifika kilele kwenye wastani 3.00
        uint256 corr = uint256(f.meanCorroborationX100);
        if (corr > 300) corr = 300;
        corr = (10 * corr) / 300;

        // Migongano ambayo haijatatuliwa: -10 kila mmoja, kikomo -25
        int256 conflicts = int256(uint256(f.openConflictCount)) * 10;
        if (conflicts > 25) conflicts = 25;

        int256 pts = int256(span + verif + breadth + corr) - conflicts;
        return _clamp(pts, 0, 100);
    }

    /**
     * @notice Kagua gates za utoshelevu wa ushahidi.
     * @return missingMask 0 = data zinatosha. Vinginevyo ni bits za MISSING_*.
     * @dev    Hii inakimbia KABLA ya hesabu yoyote. Ni BR-10, na haina njia
     *         ya kukwepwa — hakuna config, hakuna override, hakuna owner
     *         anayeweza kuizima.
     */
    function checkSufficiency(Features calldata f) public pure returns (uint8 missingMask) {
        if (f.historyMonths        < MIN_HISTORY_MONTHS)    missingMask |= MISSING_HISTORY;
        if (f.behaviourEventCount  < MIN_BEHAVIOUR_EVENTS)  missingMask |= MISSING_EVENTS;
        if (f.repaymentRecordCount < MIN_REPAYMENT_RECORDS) missingMask |= MISSING_REPAYMENTS;
        if (f.verifiedSourceCount  < MIN_VERIFIED_SOURCES)  missingMask |= MISSING_VERIFIED;
    }

    /// @dev Weka band kutokana na score, kisha weka kikomo cha dimension dhaifu.
    ///      Band hizi ni zilezile za FICO: Poor / Fair / Good / Very Good /
    ///      Exceptional — mtu yeyote anayeshawahi kusoma credit report ya
    ///      Marekani atazielewa mara moja.
    function riskBandOf(uint16 score, uint8 minDimension) public pure returns (RiskBand) {
        RiskBand b;
        if      (score < 580) b = RiskBand.POOR;
        else if (score < 670) b = RiskBand.FAIR;
        else if (score < 740) b = RiskBand.GOOD;
        else if (score < 800) b = RiskBand.VERY_GOOD;
        else                  b = RiskBand.EXCEPTIONAL;

        // Dimension yoyote chini ya 40 inazuia band kuwa bora kuliko FAIR,
        // hata kama score ya jumla iko juu.
        if (minDimension < DIMENSION_FLOOR && b >= RiskBand.GOOD) {
            b = RiskBand.FAIR;
        }
        return b;
    }

    /**
     * @notice Hesabu kamili BILA kuhifadhi chochote.
     * @dev    HII NDIYO UTAKAYOITUMIA KUJARIBU. Ni `pure` — hakuna
     *         transaction, hakuna gas, hakuna MetaMask. Remix itaionyesha
     *         kwa rangi ya buluu. Bonyeza, pata jibu papo hapo.
     *
     *         Hatua tatu:
     *         1. Kila dimension inahesabiwa 0-100.
     *         2. Uzito (30/20/15/20/15) unawekwa: weightedSum, juu kabisa 10,000.
     *         3. Min-max transformation: S = 300 + (weightedSum x 550) / 10000.
     */
    function previewScore(Features calldata f)
        public
        pure
        returns (
            uint16   score,
            uint8    d1,
            uint8    d2,
            uint8    d3,
            uint8    d4,
            uint8    d5,
            RiskBand band,
            uint8    missingMask
        )
    {
        missingMask = checkSufficiency(f);
        if (missingMask != 0) {
            // Ushahidi hautoshi. Hakuna score. Hatubahatishi.
            return (0, 0, 0, 0, 0, 0, RiskBand.NONE, missingMask);
        }

        d1 = scoreD1(f);
        d2 = scoreD2(f);
        d3 = scoreD3(f);
        d4 = scoreD4(f);
        d5 = scoreD5(f);

        // Uzito. Jumla ya juu kabisa: (30+20+15+20+15) x 100 = 10000
        uint256 weighted =
              uint256(W_D1) * d1
            + uint256(W_D2) * d2
            + uint256(W_D3) * d3
            + uint256(W_D4) * d4
            + uint256(W_D5) * d5;

        // Min-max transformation kwenda 300-850 (arXiv:2412.00710v2):
        // S = 300 + (weightedSum x 550) / 10000
        score = uint16(MIN_SCORE + (weighted * (MAX_SCORE - MIN_SCORE)) / 10000);

        uint8 minDim = d1;
        if (d2 < minDim) minDim = d2;
        if (d3 < minDim) minDim = d3;
        if (d4 < minDim) minDim = d4;
        if (d5 < minDim) minDim = d5;

        band = riskBandOf(score, minDim);
    }

    // =====================================================================
    // SEHEMU 7 — KUANDIKA KWENYE LEDGER
    // =====================================================================

    /**
     * @notice Hub inatuma features, contract inahesabu na kuhifadhi.
     * @param  borrowerRef keccak256 ya identity_hash + salt ya mfumo.
     *                     HAIWEZI kurudishwa nyuma kuwa kitambulisho.
     * @return score Score iliyohesabiwa, au 0 kama ushahidi hautoshi.
     */
    function submitFeatures(bytes32 borrowerRef, Features calldata f)
        external
        onlyHub
        returns (uint16 score, RiskBand band, uint8 missingMask)
    {
        require(borrowerRef != bytes32(0), "DAIRE: borrowerRef batili");
        _validate(f);

        uint8 d1; uint8 d2; uint8 d3; uint8 d4; uint8 d5;
        (score, d1, d2, d3, d4, d5, band, missingMask) = previewScore(f);

        if (missingMask != 0) {
            totalInsufficient += 1;
            emit InsufficientEvidence(borrowerRef, msg.sender, missingMask);
            return (0, RiskBand.NONE, missingMask);
        }

        uint32 newVersion = uint32(_history[borrowerRef].length + 1);

        Assessment memory a = Assessment({
            score:       score,
            d1:          d1,
            d2:          d2,
            d3:          d3,
            d4:          d4,
            d5:          d5,
            band:        band,
            assessedAt:  uint32(block.timestamp),
            version:     newVersion,
            submittedBy: msg.sender
        });

        // Assessment ya zamani HAIFUTWI wala kubadilishwa. Inabaki kwenye
        // historia. Marekebisho ni toleo jipya, siyo mabadiliko ya la zamani.
        _current[borrowerRef] = a;
        _history[borrowerRef].push(a);
        totalAssessments += 1;

        emit ScoreCalculated(borrowerRef, msg.sender, score, band, newVersion, a.assessedAt);
        emit DimensionsRecorded(borrowerRef, newVersion, d1, d2, d3, d4, d5);
    }

    // =====================================================================
    // SEHEMU 7B — NJIA YA PILI: SCORE ILIYO HESABIWA NJE YA CHAIN
    //
    // Njia hii ni kwa ajili ya demo/ugavi wa haraka: Hub inahesabu
    // dimensions tano nje ya chain (scoreEngine.js), kisha inatuma
    // (finalScore, dimensions) pekee. Contract HAIHESABU kitu — inahifadhi
    // tu. Inafaa wakati web app au mteja anataka kupata score kwa gharama
    // ndogo, lakini HAIFAI kama uthibitisho wa hesabu kwenye tasnifu.
    //
    // KANUNI: dimension yoyote chini ya DIMENSION_FLOOR inazuia band kuwa
    // bora kuliko FAIR, sawa kabisa na njia ya kwanza.
    // =====================================================================

    /**
     * @notice Hifadhi score iliyohesabiwa nje ya chain pamoja na dimensions
     *         tano za asili.
     * @param  borrowerRef keccak256(identity_hash | salt) — haitambui mtu.
     * @param  finalScore   300-850. Nje ya mipaka hii, transaction inarevert.
     * @param  d1           Payment Reliability      (0-100), uzito 30%
     * @param  d2           Financial Stability      (0-100), uzito 20%
     * @param  d3           Credit and Debt Mgmt     (0-100), uzito 15%
     * @param  d4           Behavioural Consistency  (0-100), uzito 20%
     * @param  d5           Verified Trust Evidence  (0-100), uzito 15%
     */
    function submitCalculatedScore(
        bytes32 borrowerRef,
        uint16 finalScore,
        uint8 d1,
        uint8 d2,
        uint8 d3,
        uint8 d4,
        uint8 d5
    ) external onlyHub returns (uint32 version) {
        require(borrowerRef != bytes32(0), "DAIRE: borrowerRef batili");
        require(finalScore >= MIN_SCORE && finalScore <= MAX_SCORE, "DAIRE: score nje ya 300-850");
        require(d1 <= 100 && d2 <= 100 && d3 <= 100 && d4 <= 100 && d5 <= 100, "DAIRE: dimension > 100");

        uint32 newVersion = uint32(_history[borrowerRef].length + 1);

        RiskBand band;
        if (useSubmittedBand) {
            band = riskBandOf(finalScore, _minDim(d1, d2, d3, d4, d5));
        }

        Assessment memory a = Assessment({
            score:       finalScore,
            d1:          d1,
            d2:          d2,
            d3:          d3,
            d4:          d4,
            d5:          d5,
            band:        band,
            assessedAt:  uint32(block.timestamp),
            version:     newVersion,
            submittedBy: msg.sender
        });

        // Assessment ya zamani HAIFUTWI wala kubadilishwa — historia niledger.
        _current[borrowerRef] = a;
        _history[borrowerRef].push(a);
        totalAssessments += 1;

        emit ScoreRecorded(borrowerRef, msg.sender, finalScore, band, newVersion, a.assessedAt);
        emit DimensionsRecorded(borrowerRef, newVersion, d1, d2, d3, d4, d5);

        return newVersion;
    }

    /// @dev Dimension ndogo zaidi kati ya tano — inatumika kwenye kizuizi cha
    ///      band (DIMENSION_FLOOR) kwenye njia ya pili.
    function _minDim(uint8 d1, uint8 d2, uint8 d3, uint8 d4, uint8 d5)
        private
        pure
        returns (uint8)
    {
        uint8 m = d1;
        if (d2 < m) m = d2;
        if (d3 < m) m = d3;
        if (d4 < m) m = d4;
        if (d5 < m) m = d5;
        return m;
    }

    /// @dev Kagua kwamba namba zilizotumwa ziko ndani ya mipaka inayokubalika.
    function _validate(Features calldata f) private pure {
        require(f.onTimeRatioBps      <= BPS, "DAIRE: onTimeRatioBps > 10000");
        require(f.activeMonthsBps     <= BPS, "DAIRE: activeMonthsBps > 10000");
        require(f.regularMonthsBps    <= BPS, "DAIRE: regularMonthsBps > 10000");
        require(f.balanceStabilityBps <= BPS, "DAIRE: balanceStabilityBps > 10000");
        require(f.utilizationBps      <= BPS, "DAIRE: utilizationBps > 10000");
        require(f.volatilityBps       <= BPS, "DAIRE: volatilityBps > 10000");
        require(f.trendBps >= -int16(int256(uint256(BPS))) && f.trendBps <= int16(int256(uint256(BPS))),
                "DAIRE: trendBps nje ya mipaka");
        require(f.verifiedSourceCount <= f.distinctSourceCount,
                "DAIRE: verified > distinct");
    }

    // =====================================================================
    // SEHEMU 8 — KUSOMA (bure — hakuna gas, API yetu itaziita hizi)
    // =====================================================================

    /// @notice Score ya sasa ya mkopaji.
    function getScore(bytes32 borrowerRef)
        external
        view
        returns (
            uint16   score,
            RiskBand band,
            uint32   assessedAt,
            uint32   version,
            bool     exists
        )
    {
        Assessment memory a = _current[borrowerRef];
        exists = a.version != 0;
        return (a.score, a.band, a.assessedAt, a.version, exists);
    }

    /// @notice Dimensions tano za assessment ya sasa.
    function getDimensions(bytes32 borrowerRef)
        external
        view
        returns (uint8 d1, uint8 d2, uint8 d3, uint8 d4, uint8 d5)
    {
        Assessment memory a = _current[borrowerRef];
        return (a.d1, a.d2, a.d3, a.d4, a.d5);
    }

    /// @notice Assessment kamili ya sasa.
    function getAssessment(bytes32 borrowerRef) external view returns (Assessment memory) {
        return _current[borrowerRef];
    }

    /// @notice Idadi ya assessments zilizowahi kutolewa kwa mkopaji huyu.
    function historyLength(bytes32 borrowerRef) external view returns (uint256) {
        return _history[borrowerRef].length;
    }

    /// @notice Assessment moja kutoka kwenye historia (index inaanzia 0).
    function getHistoryAt(bytes32 borrowerRef, uint256 index)
        external
        view
        returns (Assessment memory)
    {
        require(index < _history[borrowerRef].length, "DAIRE: index nje ya mipaka");
        return _history[borrowerRef][index];
    }

    /// @notice Historia yote kwa wakati mmoja. Tumia kwa uangalifu — mkopaji
    ///         mwenye assessments nyingi anaweza kusababisha ombi kubwa.
    function getFullHistory(bytes32 borrowerRef) external view returns (Assessment[] memory) {
        return _history[borrowerRef];
    }

    /**
     * @notice Msaidizi wa kutengeneza borrowerRef.
     * @dev    Kwenye uzalishaji, Hub ndiyo itakayohesabu hii nje ya chain
     *         ikitumia salt ya siri. Hapa ni kwa ajili ya majaribio tu.
     */
    function makeBorrowerRef(string calldata identityHash, string calldata salt)
        external
        pure
        returns (bytes32)
    {
        return keccak256(abi.encodePacked(identityHash, "|", salt));
    }

    /// @notice Maelezo ya missingMask kwa lugha ya binadamu.
    function explainMissing(uint8 missingMask) external pure returns (string memory) {
        if (missingMask == 0) return "Ushahidi unatosha";
        bytes memory s = "INSUFFICIENT_EVIDENCE:";
        if (missingMask & MISSING_HISTORY    != 0) s = abi.encodePacked(s, " historia<6mwezi");
        if (missingMask & MISSING_EVENTS     != 0) s = abi.encodePacked(s, " matukio<8");
        if (missingMask & MISSING_REPAYMENTS != 0) s = abi.encodePacked(s, " marejesho<1");
        if (missingMask & MISSING_VERIFIED   != 0) s = abi.encodePacked(s, " vyanzoVERIFIED<1");
        return string(s);
    }
}
