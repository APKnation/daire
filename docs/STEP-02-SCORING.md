# STEP 2 — DaireCreditScore.sol

**Kinachofanyika:** hesabu ya credit score **300–850** (kiwango cha kimataifa cha US) **ndani ya smart contract**, bila AI.
**Mahali pa kujaribu:** Remix VM (bure, papo hapo). Sepolia itakuja mwisho.

---

## 0. Kilichobadilishwa — sababu na uhalisia

**Uamuzi wa supervisor:** tumia range ya **300–850** kama FICO na VantageScore wanavyofanya, ili score yetu iweze kusomwa duniani kote.

**Tofauti yetu na Marekani:** hatunakili uzito wao. FICO inategemea credit bureaus zenye historia ya miaka 10+. Tanzania kuna wateja wengi wasio na mkopo wa benki, lakini wana miamala ya mobile money inayothibitisha tabia. Kwa hivyo **factors ni zilezile, uzito umebadilishwa**:

| Dimension | FICO / US | DAIRE Tanzania | Sababu ya mabadiliko |
|---|---|---|---|
| D1 Payment Reliability | 35% | **30%** | Bado ni kipengele kikuu; Marekani ina rekodi za bureaus za miaka 10+, sisi tuna vyanzo vingine vya ushahidi (D2, D5) |
| D2 Financial Stability | 0% (inatengwa) | **20%** | Mzunguko wa mobile money na akiba ndiyo uthibitisho mkuu wa uwezo wa kulipa Tanzania |
| D3 Credit & Debt Mgmt | 30% | **15%** | Watanzania wengi hawana mikopo ya benki; kutenga 30% kungewadhulumu |
| D4 Behavioural Consistency | ~15% | **20%** | Nidhamu ya miamala ya kila siku ni ishara ya kwanza kabla historia ya mikopo kuwepo |
| D5 Verified Trust Evidence | 10% (Credit Mix) | **15%** | Sybil attacks ni tishio halisi on-chain; tunahitaji vyanzo huru vyenye uthibitisho |

**Jumla ya uzito: 100%.** Hii ni ustadi wa kina unapaswa kueza kwenye tasnifu — si "kunakili FICO", ni "kubadilisha uzito kwa mazingira yetu, kwa sababu zilizochapishwa."

---

## 1. Mtiririko wa kufanya kazi

```
Andika / badilisha code
        |
        v
Compile  (Ctrl+S kwenye Remix, au button ya Compile)
        |
        v
Deploy kwenye REMIX VM          <- bure, sekunde 1, hakuna MetaMask
        |
        v
Bonyeza previewScore(...)       <- bure kabisa, ni `pure`
        |
        v
Linganisha na majibu ya §6
        |
        v  ikiwa yote ni sahihi
Deploy kwenye Sepolia           <- mara moja tu, mwisho kabisa
```

**Usibadilishe ENVIRONMENT kuwa Injected Provider bado.** Kwa hatua hii tumia **Remix VM (Cancun)** au toleo lolote la Remix VM. Ina akaunti 10 zenye 100 ETH ya kujifunzia, na kila kitu kinafanya kazi bila MetaMask.

---

## 2. Fomula kamili — hatua kwa hatua

### Hatua 2.1 — Dimension scores (0–100)

Kila dimension inahesabiwa pekee:

| Dimension | Ingizo | Uzito |
|---|---|---|
| D1 Payment Reliability | onTimeRatio, maxDaysLate, missedCount, streak | 30% |
| D2 Financial Stability | activeMonths, regularMonths, balanceStability | 20% |
| D3 Credit & Debt Mgmt | defaults, completed, utilization, lenderCount | 15% |
| D4 Behavioural Consistency | trend, volatility, recency ya tukio baya | 20% |
| D5 Verified Trust Evidence | historia, uthibitisho, upana, migongano | 15% |

### Hatua 2.2 — Weighted sum (0–10,000)

```
weightedSum = (D1 × 30) + (D2 × 20) + (D3 × 15) + (D4 × 20) + (D5 × 15)
```

Kwa sababu kila dimension ni 0–100, jumla ya juu kabisa ni 100 × 100 = **10,000**.

### Hatua 2.3 — Min-max transformation kwenda 300–850

Tunatumia mbinu ya min-max normalization (arXiv:2412.00710v2):

```
S = S_min + (weightedSum × (S_max − S_min)) / W_max
S = 300   + (weightedSum × 550)           / 10,000
```

| Kipimo | Thamani | Maana |
|---|---|---|
| S_min | 300 | Mkopaji mbovu kabisa anapata 300 (sio 0) |
| S_max | 850 | Mkopaji mbora kabisa anapata 850 |
| Range | 550 | 850 − 300 |
| W_max | 10,000 | Jumla ya juu ya weightedSum |

**Kwa nini hatuanzi 0?** Kwa sababu FICO na VantageScore vyote vinaanza 300 — mtu asiye na historia yoyote hupata 300, sio sifuri. Hii ni ishara kwamba "hatukujui" ni tofauti na "hatukuombi".

### Hatua 2.4 — RiskBand (mpangilio wa FICO)

| Band | Score | Jina |
|---|---|---|
| 0 | — | NONE (ushahidi hautoshi) |
| 1 | 300–579 | POOR |
| 2 | 580–669 | FAIR |
| 3 | 670–739 | GOOD |
| 4 | 740–799 | VERY_GOOD |
| 5 | 800–850 | EXCEPTIONAL |

### Hatua 2.5 — Kizuizi cha dimension dhaifu

Ikiwa dimension yoyote iko **chini ya 40**, band haiwezi kuwa bora kuliko FAIR, hata kama score ya jumla iko juu. Hii ni kuzuia mtu asiyelipa mikopo yake kupata "GOOD" kwa sababu tu ana miamala mizuri ya simu.

---

## 3. Mfano wa hesabu kamili — mkopaji "Juma"

Features za Juma (zimetokana na data ya mobile money + wallet yake):

```
D1 = 85  (analipa kwa wakati 90%+)
D2 = 70  (akiba na mzunguko uko vizuri)
D3 = 80  (utilization 40%, hakuna default)
D4 = 65  (miezi 18 ya miamala bila kukatika)
D5 = 75  (akaunti imethibitishwa na vyanzo 2)
```

### 3.1 Weighted sum

```
weightedSum = (85 × 30) + (70 × 20) + (80 × 15) + (65 × 20) + (75 × 15)
            = 2550      + 1400      + 1200      + 1300      + 1125
            = 7575
```

### 3.2 Kubadilisha kwenda 300–850

```
S = 300 + (7575 × 550) / 10000
  = 300 + 4,166,250 / 10000
  = 300 + 416.625
  = 716.625  →  hupunguzwa hadi 716 (Solidity inakata desimali)
```

**Score ya Juma = 716 → GOOD (670–739).**

Ukiongeza uzito wa FICO (35/30/15/10/10) kwa dimensions zilezile, Juma angepata:

```
(85×35 + 70×0 + 80×30 + 65×15 + 75×10) / 100 = 7.925 → 790
```

Tofauti hii ndiyo maneno ya uzito yetu: FICO inampenda watu wanaotumia mkopo sana (D3=30%), sisi tunapenda wale wenye uthabiti wa fedha hata kama hawajawahi kukopa benki (D2=20%).

---

## 4. Sehemu nane za contract

| Sehemu | Ndani yake |
|---|---|
| 1 — Constants | Kila kanuni ya scoring kama `public constant`, ili ikaguliwe kutoka Etherscan |
| 2 — Aina za data | `enum RiskBand`, `struct Features` (namba 21), `struct Assessment` |
| 3 — Storage | `owner`, `authorizedHubs`, assessment ya sasa, historia |
| 4 — Events | `ScoreCalculated`, `DimensionsRecorded`, `InsufficientEvidence` |
| 5 — Access control | `onlyOwner`, `onlyHub` |
| 6 — Hesabu | `scoreD1` … `scoreD5`, `checkSufficiency`, `previewScore` — zote `pure` |
| 7 — Kuandika ledger | `submitFeatures` — hii pekee ndiyo inayogharimu gas |
| 8 — Kusoma | `getScore`, `getDimensions`, historia — zote bure |

---

## 5. Mpangilio wa fields — MUHIMU

Kwenye Remix, `struct` inaingizwa kama **tuple** ndani ya mabano ya mraba. Mpangilio lazima ufanane kabisa na ulivyo kwenye contract:

| # | Field | Aina | Maana |
|---|---|---|---|
| 1 | `historyMonths` | uint16 | Miezi ya historia inayoonekana |
| 2 | `behaviourEventCount` | uint16 | Jumla ya matukio ya kitabia |
| 3 | `repaymentRecordCount` | uint16 | Rekodi za marejesho au miamala |
| 4 | `verifiedSourceCount` | uint8 | Vyanzo vyenye status VERIFIED |
| 5 | `onTimeRatioBps` | uint16 | Kulipa kwa wakati — **9750 = 97.50%** |
| 6 | `maxDaysLate` | uint16 | Siku nyingi zaidi za kuchelewa |
| 7 | `missedCount` | uint16 | Marejesho yaliyokosekana kabisa |
| 8 | `onTimeStreak` | uint16 | Mfululizo wa sasa wa kulipa kwa wakati |
| 9 | `activeMonthsBps` | uint16 | Miezi yenye muamala 1+ (bps) |
| 10 | `regularMonthsBps` | uint16 | Miezi yenye miamala 4+ (bps) |
| 11 | `balanceStabilityBps` | uint16 | Uthabiti wa salio (juu = thabiti) |
| 12 | `defaultCount` | uint16 | Mikopo iliyoingia default (miezi 36) |
| 13 | `completedCount` | uint16 | Mikopo iliyokamilika |
| 14 | `utilizationBps` | uint16 | Matumizi ya mkopo (bps) |
| 15 | `activeLenderCount` | uint8 | Taasisi zenye mkopo hai |
| 16 | `trendBps` | **int16** | Mwelekeo — **inaweza kuwa hasi** |
| 17 | `volatilityBps` | uint16 | Kuyumba (juu = mbaya) |
| 18 | `monthsSinceAdverse` | uint16 | Miezi tangu tukio baya; **65535 = hakuna kamwe** |
| 19 | `distinctSourceCount` | uint8 | Vyanzo huru vyote |
| 20 | `meanCorroborationX100` | uint16 | Wastani wa uthibitisho — **250 = 2.50** |
| 21 | `openConflictCount` | uint8 | Migongano isiyotatuliwa |

> **Kanuni tatu za kukumbuka**
> - Asilimia zote ni **basis points**: 10000 = 100%. Solidity haina desimali.
> - `monthsSinceAdverse` = **65535** ikiwa mkopaji hajawahi kuwa na tukio baya.
> - `verifiedSourceCount` haiwezi kuzidi `distinctSourceCount` — contract itakataa.

---

## 6. Test vectors — majibu ya kutarajia

Majibu haya yamehakikiwa kwa script ya hesabu inayofanana kabisa na logic ya contract. **Kama jibu lako linatofautiana na hapa, kuna kosa** — niambie.

### A — Mkopaji bora

```
[34,48,34,3,9900,3,0,18,10000,9166,8200,0,3,4200,2,1500,900,65535,3,260,0]
```

| Matokeo | Thamani |
|---|---|
| score | **796** |
| D1 · D2 · D3 · D4 · D5 | 100 · 91 · 100 · 63 · 96 |
| band | `4` = VERY_GOOD |
| missingMask | 0 |

*Anaripoti kwa wakati 99%, hakuna default, mikopo 3 imekamilika, utilization 42% (eneo zuri), vyanzo 3 vilivyothibitishwa. Score 796 ni VERY_GOOD — anahitaji 800 kwa EXCEPTIONAL.*

### B — Mkopaji wa wastani

```
[18,22,16,1,9100,27,1,5,9166,5000,6000,0,1,7600,3,400,2500,14,2,150,0]
```

| Matokeo | Thamani |
|---|---|
| score | **632** |
| D1 · D2 · D3 · D4 · D5 | 60 · 69 · 85 · 37 · 57 |
| band | `2` = FAIR |

*Score 632 ni FAIR na band ni FAIR. Ikiwa hakuna kizuizi, ingekuwa FAIR vilevile — lakini **D4 = 37, chini ya 40**, kwa hivyo hawezi kufika GOOD hata kama score ingeongezeka. Hiki ndicho kizuizi cha dimension dhaifu kikifanya kazi.*

### C — Mkopaji hatari

```
[26,31,24,1,6500,95,6,0,6666,2500,3000,2,0,9600,4,-3000,7000,4,2,110,2]
```

| Matokeo | Thamani |
|---|---|
| score | **384** |
| D1 · D2 · D3 · D4 · D5 | 0 · 42 · 0 · 3 · 43 |
| band | `1` = POOR |

*Default 2, kuchelewa siku 95, utilization 96%, taasisi 4 kwa wakati mmoja, mwelekeo hasi, tukio baya miezi 4 iliyopita, migongano 2 haijatatuliwa. Score 384 ni POOR (300–579).*

> Kumbuka `trendBps = -3000`. Ndiyo maana field hii ni `int16` na siyo `uint16` — mwelekeo unaweza kuwa hasi.

### D — Ushahidi hautoshi

```
[3,4,1,0,10000,0,0,3,10000,10000,10000,0,0,3000,1,0,0,65535,1,100,0]
```

| Matokeo | Thamani |
|---|---|
| score | **0** |
| band | `0` = NONE |
| missingMask | **11** |

*Angalia: mkopaji huyu ana rekodi **kamilifu** — onTimeRatio 100%, hakuna default. Lakini ana miezi 3 tu ya historia na matukio 4. Mfumo **unakataa kutoa score.*** Score 0 maana yake ni "hakuna score" — sio "score ya chini kabisa". Mkopaji aliyekaguliwa anaanza 300.

`missingMask = 11` ni binary `1011`:

| Bit | Thamani | Maana |
|---|---|---|
| 1 | ✓ | historia chini ya miezi 6 |
| 2 | ✓ | matukio chini ya 8 |
| 4 | ✗ | marejesho yanatosha |
| 8 | ✓ | hakuna chanzo kilichothibitishwa |

Jaribu `explainMissing(11)` → `"INSUFFICIENT_EVIDENCE: historia<6mwezi matukio<8 vyanzoVERIFIED<1"`

**Hiki ndicho kipengele chenye thamani kubwa zaidi kwenye tasnifu yako.** Hakuna mfumo wa dunia tuliouchunguza unaochapisha sheria ya wazi ya kukataa kutoa score. Wote wanatoa namba ndogo au "unscoreable" bila kueleza kanuni.

### E — Kizuizi cha dimension dhaifu

```
[36,60,40,3,7000,60,4,0,10000,10000,10000,0,2,4000,1,8000,0,65535,3,300,0]
```

| Matokeo | Thamani |
|---|---|
| score | **667** |
| D1 · D2 · D3 · D4 · D5 | **0** · 100 · 100 · 84 · 100 |
| band | `2` = FAIR |

*Dimensions nne ni bora kabisa. Lakini tabia ya ulipaji ni mbaya: D1 = 0. Score 667 ingempa FAIR hata bila kizuizi — kizuizi kinahakikisha hawezi kufika GOOD au juu zaidi. Ni sawa — mtu asiyelipa mikopo yake hapaswi kuwa "hatari ndogo" kwa sababu tu ana miamala mizuri.*

---

## 7. Kujaribu kuhifadhi kwenye ledger

`previewScore` **haihifadhi chochote**. Ili kuandika kwenye ledger, tumia `submitFeatures` (rangi ya machungwa — inagharimu gas).

**1.** Tengeneza borrowerRef. Bonyeza `makeBorrowerRef` na uweke:
```
identityHash: "test-mkopaji-001"
salt:         "daire-salt-dev"
```
Nakili `bytes32` inayotoka.

**2.** Bonyeza `submitFeatures`, weka:
```
borrowerRef: <ile bytes32>
f:           [34,48,34,3,9900,3,0,18,10000,9166,8200,0,3,4200,2,1500,900,65535,3,260,0]
```

**3.** Bonyeza **transact**. Kwenye Remix VM hakuna MetaMask — inafanyika papo hapo.

**4.** Fungua terminal ya Remix chini. Panua transaction → **`logs`**. Utaona:
- `ScoreCalculated` — score 796, band 4 (VERY_GOOD), version 1
- `DimensionsRecorded` — 100, 91, 100, 63, 96

Hii ndiyo "ledger" — data yako imeandikwa na haiwezi kubadilishwa.

**5.** Sasa soma: `getScore(<borrowerRef>)` → score 796. `getDimensions(...)` → dimensions tano. `historyLength(...)` → 1.

**6. Jaribio la muhimu:** tuma `submitFeatures` tena kwa borrowerRef **ileile**, lakini na features za mkopaji C (score 384).

Kisha:
- `getScore` → 384 (ya sasa)
- `historyLength` → **2**
- `getHistoryAt(ref, 0)` → **796 bado ipo**

*Rekodi ya zamani **haijafutwa wala kubadilishwa**. Ni toleo la pili. Hii ndiyo tabia ya append-only ambayo SRS inaitaka, na ndiyo inayofanya audit iwezekane.*

---

## 8. Jaribio la access control

**1.** Kwenye Remix VM, badilisha **ACCOUNT** (juu ya panel ya Deploy) kwenda akaunti ya pili.

**2.** Jaribu `submitFeatures` tena.

**3.** Itakataa: `DAIRE: Hub haijaruhusiwa`

**4.** Rudi kwenye akaunti ya kwanza (owner), bonyeza `setHub(<anwani ya akaunti ya pili>, true)`.

**5.** Rudi kwenye akaunti ya pili — sasa inafanya kazi.

*Bila kizuizi hiki, mtu yeyote angeweza kutuma namba za uongo na kujipatia score ya 850.*

---

## 9. Jedwali la uzito na kwa nini limetofautiana na FICO

| Dimension | Uzito wetu | FICO | Sababu |
|---|---|---|---|
| D1 Payment Reliability | **30%** | 35% | Bado kikuu, lakini tuna vyanzo vingine vya ushahidi |
| D2 Financial Stability | **20%** | 0% (nje ya score) | Mobile money na akiba ndiyo ushahidi mkuu TZ |
| D3 Credit & Debt Mgmt | **15%** | 30% | Wengi hawana mikopo ya benki |
| D4 Behavioural Consistency | **20%** | ~15% | Nidhamu ya kila siku ni ishara ya kwanza TZ |
| D5 Verified Trust Evidence | **15%** | 10% (Credit Mix) | Sybil attacks ni tishio halisi on-chain |

Uzito wa 30% kwa D1 siyo wa kubahatisha. FICO inatoa 35% kwa payment history; OCCR inatoa 35% kwa historical credit risk; VantageScore inaiita kipengele pekee chenye ushawishi *extremely influential*. Tumepunguza kidogo kwa sababu tunatumia vyanzo vingine — lakini bado ni kikubwa kuliko vyote.

### Kupungua kwa adhabu ya tukio baya

`40 × 0.5 ^ (miezi / 12)`

| Miezi tangu tukio | Adhabu |
|---|---|
| 0 | −40 |
| 6 | −30 |
| 12 | −20 |
| 18 | −15 |
| 24 | −10 |
| 36 | −5 |
| 48 | −2 |
| 72+ | 0 |

Jaribu mwenyewe: `adversePenalty(24)` → `10`.

Fomula hii imechapishwa, kwa hivyo mkopaji anaweza kuambiwa **hasa** default yake itaacha kumuathiri lini. ARCx inafanya kitu kama hiki lakini kwa kukata ghafla baada ya siku 120; yetu inapungua taratibu.

---

## 10. Checklist ya Step 2

- [ ] `DaireCreditScore.sol` ime-compile bila makosa
- [ ] `RULESET_VERSION` inaonyesha `DAIRE-RULES-2.0-US-RANGE`
- [ ] `MIN_SCORE` = 300, `MAX_SCORE` = 850
- [ ] Ime-deploy kwenye Remix VM
- [ ] `previewScore` inatoa majibu sahihi kwa A, B, C, D, E
- [ ] `explainMissing(11)` inaeleza vizuri
- [ ] `adversePenalty(24)` = 10
- [ ] `submitFeatures` inaandika, `ScoreCalculated` inaonekana kwenye logs
- [ ] `getScore` inarudisha kile kilichoandikwa
- [ ] Toleo la pili linahifadhi la kwanza kwenye historia
- [ ] Akaunti isiyoruhusiwa inakataliwa
- [ ] `setHub` inaruhusu akaunti mpya

---

## 11. Kujitetea mbele ya supervisor — hoja tano

Ukichukuliwa maswali, hizi ndizo hoja kuu:

1. **Standardization.** Range ya 300–850 na bands za Poor/Fair/Good/Very Good/Exceptional ni kiwango kinachoeleweka duniani kote — FICO na VantageScore vyote vinatumia. Mtengenezaji wa mikopo wa nchi yoyote anasoma score yetu bila mafunzo.
2. **Contextual adaptation.** Hatukunakili uzito wa FICO (35/30/15/10/10). Tumeunda 30/20/15/20/15 kwa sababu zilizo na ushahidi: Tanzania kuna wateja wengi wasio na mkopo wa benki, mobile money ni ushahidi mkuu, na sybil attacks ni tishio halisi on-chain.
3. **Mathematical rigor.** Transformation ya min-max imechapishwa kwenye utafiti (arXiv:2412.00710v2) na imetekelezwa kwa hesabu kamili ya integer — hakuna desimali, hakuna kosa la mviringo zaidi ya kimoja.
4. **Determinism.** Inputs zilezile zinatoa score ileile, milele. Contract haina randomness, hakuna AI, hakuna owner anayeweza kubadilisha score ya mkopaji aliyeshaohifadhiwa.
5. **Explainability.** Kila score ina dimensions tano (D1–D5), bands tano, na kanuni zilizochapishwa. Mkopaji anaweza kuambiwa **hasa** kwa nini alipata 632 badala ya 700 — jambo ambalo FICO wenyewe halitolewi bure.

---

## 12. Kinachofuata

| Step | Kinachofanyika |
|---|---|
| 3 | Gas optimisation, packing ya struct, kupunguza gharama |
| 4 | Unit tests za kweli (Remix `tests/` folder) |
| 5 | Deploy Sepolia + thibitisha Etherscan |
| 6 | Django integration kupitia web3.py |
| 7 | AI analysis layer juu ya scores zilizohifadhiwa |
