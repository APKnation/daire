# Architecture — Where the Credit Score Is Calculated

**Project:** DAIRE — Decentralized AI Reputation Engine
**Decision:** the credit score is calculated **on-chain, inside the smart contract** (supervisor requirement).

---

## 0. Mtandao wa walipa — NMB + CRDB pekee

DAIRE inaunganisha **benki mbili tu**: **NMB Bank Microfinance** (`LDR-NMB-02`) na **CRDB Bank Plc** (`LDR-CRDB-01`).

- Kila benki ina subsystem yake inayotuma data kwenda `POST /api/lender-data/receive/` na kupokea matokeo kupitia webhook.
- **Muunganisho wa mteja (borrower merge) unafanyika kwenye `nida_number`** — kama mteja yuleyule yuko NMB na CRDB, data zote mbili zinaingia kwenye rekodi moja ya central, na assessment moja inapimwa kwenye data iliyounganishwa (AI + blockchain).
- Kiasi cha mkopo anachotaka (applied loan amount) kinatumwa na benki kwenye push (`payload.loan_application`) na ndicho exposure inayopimwa.
- Walipa wengine (Equity, Tigo, Airtel, Mwanga…) wameondolewa kabisa: hawana rekodi kwenye database (`python manage.py prune_lenders --yes`), hawana seed data, na mock endpoints zinawarudishia 404.

---

## 1. Uamuzi na maana yake

Supervisor amesema hesabu ya credit score ifanyike ndani ya project — yaani **ndani ya smart contract**. Hii ni tofauti na mifumo mingi ya dunia (Spectral, Cred Protocol) inayohesabu nje ya chain kisha kuandika matokeo tu.

Uamuzi huu una faida tatu kubwa kwa tasnifu:

1. **Hesabu inaweza kukaguliwa na mtu yeyote.** Code iko wazi kwenye Etherscan; mtu yeyote anaweza kuthibitisha kwamba score ni sahihi.
2. **Hakuna mtu anayeweza kubadilisha score.** Hata sisi wenyewe. Ni deterministic — inputs zilezile zinatoa score ileile, kila wakati.
3. **Ni mchango halisi.** Utafiti wetu (`DAIRE/RES/003`) umeonyesha kwamba karibu hakuna mfumo unaohesabu score ndani ya contract. Sisi tunafanya.

Lakini una gharama moja kubwa ambayo lazima tuishughulikie kwa uangalifu — **kila kitu kinachoenda on-chain ni cha umma milele.**

---

## 2. Kanuni ya dhahabu

> **Hakuna data binafsi inayoenda on-chain. Namba zilizokokotolewa tu (derived integers).**

Central System (Credit Information Hub) inashikilia data ghafi. Contract inapokea **matokeo ya hesabu ya awali** pekee — namba ambazo hazimtambulishi mtu.

| Kinachobaki PostgreSQL (off-chain) | Kinachoenda on-chain |
|---|---|
| Jina la mteja | — |
| Namba ya kitambulisho | `bytes32 borrowerRef` (hash pekee) |
| Namba ya simu, anwani | — |
| Kiasi cha mkopo (TZS) | — |
| Tarehe za marejesho | — |
| Rekodi za miamala | — |
| Jina la taasisi | `address institution` (anwani ya wallet) |
| — | `onTimeRatio` (0–10000, basis points) |
| — | `maxDaysLate`, `missedCount` |
| — | `defaultCount`, `completedCount` |
| — | `utilizationBps` |
| — | `activeLenderCount` |
| — | `historyMonths` |
| — | `verifiedSourceCount`, `distinctSourceCount` |
| — | `behaviourEventCount` |
| — | `openConflictCount` |

`borrowerRef` ni `keccak256` ya `identity_hash` yetu pamoja na salt ya mfumo. Haiwezi kurudishwa nyuma kuwa kitambulisho, lakini inatosha kumtambua mteja yuleyule mara ya pili.

---

## 3. Mtiririko kamili

```
[1] LENDER SYSTEMS — NMB na CRDB tu
      zinatuma rekodi ghafi (push au pull)
      |
      v  POST /api/lender-data/receive/   (consent inakaguliwa hapa)
[2] DJANGO + DRF  —  Credit Information Hub  (PostgreSQL: daire @ :5433)
      - validation
      - NIDA merge: data za NMB + CRDB kwenye borrower mmoja
      - consent enforcement
      - evidence + SHA-256
      |
      v
[3] POSTGRESQL   —  system of record (data ghafi zinaishia hapa)
      loans · repayments · transactions · evidence · behaviour_events
      |
      v  inasoma
[4] PYTHON FEATURE BUILDER
      inageuza rekodi ghafi ZILIZOUNGANISHWA (NMB + CRDB) kuwa NAMBA ZISIZOMTAMBULISHA MTU:
        on_time_ratio          = 9750   (yaani 97.50% — marejesho ya benki zote mbili)
        max_days_late          = 12
        missed_count           = 1
        default_count          = 0
        completed_count        = 3
        utilization_bps        = 4200   (yaani 42.00%)
        active_lender_count    = 2      (NMB + CRDB)
        history_months         = 28
        verified_source_count  = 2
        distinct_source_count  = 3
        behaviour_event_count  = 41
        open_conflict_count    = 0
        applied_loan_amount    = 500000 (kiasi anachotaka — exposure inayopimwa)
      |
      v  web3.py, imesainiwa na Hub key
[5] SMART CONTRACT  —  DaireCreditScore.sol   *** HAPA NDIPO SCORE INAPOHESABIWA ***
      submitFeatures(borrowerRef, features)
        -> checkSufficiency()      gates: miezi 6, matukio 8, chanzo 1 VERIFIED
        -> _scoreD1() .. _scoreD5()
        -> weightedSum = (30*D1 + 20*D2 + 15*D3 + 20*D4 + 15*D5)   # max 10,000
        -> score = 300 + (weightedSum * 550) / 10000              # min-max: 300-850
        -> band = _riskBand(score)   # POOR/FAIR/GOOD/VERY_GOOD/EXCEPTIONAL (FICO)
        -> storage: scores[borrowerRef] = Assessment{...}
        -> history[borrowerRef].push(...)
        -> emit ScoreCalculated(...)
      |
      v
[6] LEDGER  —  Sepolia
      score, dimensions, band, timestamp, version — vyote vya umma na visivyobadilika
      |
      v  contract.functions.getScore(borrowerRef).call()
[7] DJANGO API
      GET /api/borrowers/search/  (unified borrower: accounts, loans, loan_applications[])
      inasoma score kutoka chain, inaunganisha na explanation ya PostgreSQL
      |
      v
[8] AI ANALYSIS LAYER
      inachukua score kutoka chain + behaviour za ziada kutoka PostgreSQL
      inafanya uchambuzi wa kina, trends, na mapendekezo
```

## 3.1 KANUNI YA DHAHABU — matokeo ya AI na blockchain yanapita KWENYE CENTRAL KWANZA

Engines haziwahi kuwasiliana na benki moja kwa moja. Mtiririko ni huu, kwa mpangilio huu:

```
[1] Central inafungua assessment kwenye borrower ALIYOUNGANISHWA (NIDA: NMB + CRDB)
[2] Central -> AI:      POST /api/assessments/{ref}/ai-reputation/
      matokeo yanahifadhiwa CENTRAL KWANZA (core_aireputationresult)
[3] Central -> Chain:   POST /api/assessments/{ref}/blockchain-score/
      matokeo yanahifadhiwa CENTRAL KWANZA (core_smartcontractresult
      + core_blockchaintransaction — tx hash ya on-chain ndiyo uthibitisho)
[4] BILDI YA MWISHO:    POST /api/borrowers/{id}/broadcast-result/
      inasoma matokeo yote mawili YA ASSESSMENT ILEILE kutoka kwenye storage,
      inayafunga kwenye bahasha moja (results.ai + results.blockchain),
      inaandika DataExchange (audit), KISHA inasukuma kwa NMB/CRDB
```

Udhibiti uliotekelezwa kwenye code (`broadcast_result`):

- Kupasha bila matokeo yaliyohifadhiwa -> **409** ("Score first, then broadcast"). Benki haiwezi kupokea result Central isiyokuwa nayo.
- Matokeo ya engine zote mbili yanatoka kwenye **assessment moja** — hakuna kuchanganya score mpya ya chain na score ya zamani ya AI.
- Kila push inaandikwa `core_dataexchange` — Central inajua kilichotoka, lini, na kwa nani.
- Benki zinapata matokeo kwa **kuuliza Central** (`/api/borrowers/search/`, `/api/assessments/{ref}/ai-result/`), siyo kwa kuuliza engines moja kwa moja.

Kwa nini kanuni hii ni muhimu:

1. **Audit** — kila result inayofika benki ina nakala yake kwenye Central yenye timestamp, model_version, na tx hash. Mzozo wowote unatatuliwa kwa kulinganisha na Central.
2. **Usalama** — engines (AI model, blockchain RPC) hazipati anwani za benki wala la kujua walipa wahusika. Nguvu ya kusambaza ni ya Central pekee.
3. **Ubora wa data** — benki inapokea result iliyounganishwa (NMB + CRDB pamoja) kutoka kwenye assessment moja, siyo vipande vya engine tofauti.

---

## 4. Nani anaruhusiwa kufanya nini

Access control ni muhimu sana. Bila hiyo, mtu yeyote anaweza kutuma features za uongo na kujipatia score nzuri.

| Jukumu | Anaruhusiwa | Utekelezaji |
|---|---|---|
| **Owner** (sisi) | Kuongeza/kuondoa Hub, kusimamisha contract | `onlyOwner` modifier |
| **Hub** (Central System) | Kutuma features na kuanzisha hesabu | `onlyHub` modifier + mapping ya `authorizedHubs` |
| **Mtu yeyote** | Kusoma score, dimensions, historia | `view` functions, bila kizuizi |
| **Taasisi** | Kusoma kupitia API yetu | Off-chain, kupitia consent |

Contract itakuwa na `mapping(address => bool) public authorizedHubs`. Hub key inahifadhiwa kwenye server, **haiwekwi kamwe kwenye Git**.

---

## 5. Kwa nini basis points na siyo desimali

Solidity **haina namba za desimali**. Hakuna `float`, hakuna `0.975`.

Suluhisho la kawaida ni **basis points** — kuzidisha kwa 10,000 na kutumia integer:

| Maana halisi | Kwenye Solidity | Aina |
|---|---|---|
| 97.50% | `9750` | `uint16` |
| 42.00% | `4200` | `uint16` |
| 100.00% | `10000` | `uint16` |
| 0.5 (recency decay) | inatekelezwa kwa mgawanyiko wa hatua | tazama Step 2 |

Kanuni: **gawanya mwisho kabisa.** `(a * b) / c` siyo `(a / c) * b` — mgawanyiko wa mapema unapoteza usahihi.

---

## 6. Gharama ya gas

Hesabu ndani ya contract inagharimu gas. Makadirio ya awali kwa Sepolia:

| Operesheni | Makadirio ya gas | Kumbuka |
|---|---|---|
| Deployment | 1,500,000 – 2,500,000 (makadirio) | **Halisi: 3,922,043** (Sepolia, 2026-09-11) |
| `submitFeatures` + hesabu | 150,000 – 300,000 | Kila assessment |
| `getScore` (view) | 0 | Bure kabisa |

Kwenye Sepolia hii haina gharama halisi. Kwenye mainnet ingekuwa ghali — na hii ndiyo sababu miradi mingi ya kibiashara inahesabu nje ya chain. Kwenye tasnifu, **taja hili kama limitation na jadili mbadala** (Layer 2 kama Polygon au Arbitrum ingepunguza gharama kwa zaidi ya 90%).

---

## 7. Mambo ya kuzingatia kwenye tasnifu

Andika haya kwa uwazi — ni sehemu ya uchambuzi wa kina:

1. **Score ya umma.** Kwa sababu tunaandika score on-chain, ni ya umma. Tunailinda kwa `borrowerRef` iliyo hash — hakuna anayejua ni nani. Lakini taasisi iliyotuma data inajua ramani hiyo.
2. **Sheria ya kufuta baada ya miaka 6.** Kanuni 36 ya BoT inataka taarifa mbaya ziondolewe baada ya miaka sita. Blockchain haifuti. **Suluhisho letu:** tunafuta ramani ya `borrowerRef` kwenye PostgreSQL. Baada ya hapo, namba iliyobaki on-chain haiwezi kuunganishwa na mtu yeyote — ni sawa na kufutwa kiutendaji (*cryptographic erasure*).
3. **Marekebisho.** Score isiyo sahihi haiwezi kufutwa; tunaongeza assessment mpya yenye version kubwa zaidi. Historia yote inabaki kwa ajili ya audit.
4. **Toleo la kanuni.** Kila score inahifadhiwa na `rulesetVersion`. Tukibadilisha uzito, tuna-deploy contract mpya — score za zamani zinabaki zikiwa zimehesabiwa kwa kanuni zilizokuwepo wakati huo.

---

## 8. Muhtasari kwa neno moja

**PostgreSQL** = data ghafi na maelezo.
**Feature builder** = kugeuza data kuwa namba.
**Smart contract** = kuhesabu score na kuihifadhi.
**API** = kusoma score na kuiunganisha na maelezo.
**AI** = uchambuzi wa ziada juu ya score na tabia.
