# DAIRE — Smart Contracts

**Decentralized AI Reputation Engine**
On-chain credit scoring for decentralized credit assessment.

---

## Nini kinaendelea hapa

Contract hizi zinahesabu **credit score ya 300–850 (kiwango cha kimataifa, kama FICO na VantageScore) ndani ya smart contract yenyewe**, kwa uzito uliorekebishwa kwa mazingira ya Tanzania, kutoka kwenye features zinazotumwa na Credit Information Hub (Central System), kisha zinahifadhi matokeo kwenye ledger na kuyatoa kupitia read functions ambazo API yetu inaziita.

Hesabu inafanyika on-chain kwa makusudi — ili iweze kukaguliwa na mtu yeyote na isiweze kubadilishwa na yeyote, sisi tukiwemo.

---

## Zana

```
[ VS Code ] --remixd--> [ Remix IDE ] --> [ MetaMask ] --> [ Sepolia ] --> [ Etherscan ]
  andika code            compile           saini tx        tekeleza        kagua
```

| Zana | Matumizi |
|---|---|
| VS Code | Kuandika code |
| remixd | Kushiriki folder hii na Remix IDE |
| Remix IDE | Compile na deploy |
| MetaMask | Kusaini transactions |
| Sepolia testnet | Kutekeleza bure |
| Sepolia Etherscan | Kuthibitisha matokeo |

---

## Muundo wa folder

```
daire-contracts/
├── contracts/
│   ├── DaireHandshake.sol      Step 1 — pipeline test (hakuna scoring)
│   └── DaireCreditScore.sol    Step 2 — scoring logic  [inakuja]
├── docs/
│   ├── STEP-01-SETUP.md        Mwongozo kamili wa hatua kwa hatua
│   └── ARCHITECTURE.md         Data zinatoka wapi na zinaenda wapi
├── deployments/
│   └── README.md               Rekodi ya anwani za contracts
├── scripts/                    [inakuja]
├── test/                       [inakuja]
├── .vscode/                    Mapendekezo ya extensions na settings
├── .gitignore
└── package.json
```

---

## Anza hapa

**Fungua `docs/STEP-01-SETUP.md` na fuata hatua kwa hatua.**

Kwa haraka:

```bash
# 1. Weka remixd
npm install -g @remix-project/remixd

# 2. Shiriki folder hii na Remix
npm run remixd

# 3. Fungua https://app.remix.live
#    File Explorer -> workspace dropdown -> "- connect to localhost -"
```

---

## Hatua za mradi

| Step | Kinachofanyika | Hali |
|---|---|---|
| **1** | Initialization, remixd, deploy `DaireHandshake`, thibitisha Etherscan | 🔵 Unaendelea |
| 2 | `DaireCreditScore.sol` — struct, access control, hesabu ya D1–D5, score 300–850 | ⚪ Inasubiri |
| 3 | Storage, historia, events, gas optimisation | ⚪ |
| 4 | Testing — unit tests na edge cases | ⚪ |
| 5 | Django integration kupitia web3.py | ⚪ |
| 6 | Source verification kwenye Etherscan | ⚪ |
| 7 | AI analysis layer juu ya scores | ⚪ |

---

## Kanuni ya usalama isiyovunjwa

**Hakuna private key, seed phrase, au `.env` inayoingia kwenye folder hii.**

`.gitignore` inazuia, lakini kizuizi halisi ni tabia yako. Wallet ya mradi huu iwe **mpya kabisa**, isiyo na fedha halisi, ikitumika kwa Sepolia pekee.

---

## Nyaraka za mradi

| Waraka | Kitambulisho |
|---|---|
| Software Requirements Specification | DAIRE/SRS/001 |
| System Design Document | DAIRE/SDD/001 |
| Data Collection Specification | DAIRE/DCS/001 |
| Credit scoring data research | DAIRE/RES/001 |
| On-chain scoring research | DAIRE/RES/003 |
