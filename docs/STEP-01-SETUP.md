# STEP 1 — Project Initialization and Deployment Pipeline

**Project:** DAIRE — Decentralized AI Reputation Engine
**Document:** `docs/STEP-01-SETUP.md`
**Goal of this step:** kuthibitisha kwamba mnyororo mzima wa zana unafanya kazi, kabla hatujaandika logic ya credit score.

---

## 0. Tunachothibitisha kwenye hatua hii

```
[ VS Code ]  --remixd-->  [ Remix IDE ]  -->  [ MetaMask ]  -->  [ Sepolia ]  -->  [ Etherscan ]
  andika          shiriki folder      compile        saini tx      tekeleza       ona matokeo
```

Mwishoni mwa hatua hii utakuwa na:

- Folder ya project kwenye computer yako, inayofunguliwa na VS Code
- Remix IDE ikisoma **files zilezile** za computer yako (siyo nakala)
- Contract iliyo-deploy kwenye Sepolia testnet, yenye anwani halisi
- Transaction inayoonekana kwenye Sepolia Etherscan
- Uthibitisho kwamba unaweza **kubadilisha hali ya blockchain** kutoka kwenye code yako

> Contract ya hatua hii (`DaireHandshake.sol`) **haihesabu credit score**. Hiyo ni Step 2. Hii ni kuthibitisha njia tu — usirukie mbele.

---

## 1. Prerequisites

Fungua terminal ya VS Code (`Ctrl + \``) kwenye folder ya project, kisha thibitisha kila kimoja:

| Kinachohitajika | Amri ya kuthibitisha | Kinachotarajiwa |
|---|---|---|
| Node.js | `node -v` | `v18.x` au juu zaidi |
| npm | `npm -v` | `9.x` au juu zaidi |
| PostgreSQL 18 | `pg_isready -p 5433` | `accepting connections` |
| Browser | Chrome / Brave / Firefox | Yoyote inayokubali MetaMask |

### 1.1 PostgreSQL — database ya Central System

Central System inatumia **PostgreSQL 18 kwenye port `5433`**, database **`daire`**, mtumiaji **`daire`**:

```bash
# Hakikisha server inaendelea (Ubuntu):
sudo systemctl status postgresql
pg_isready -h 127.0.0.1 -p 5433        # -> accepting connections

# Tengeneza role + database (mara moja tu). Badilisha nenosiri:
sudo -u postgres psql -p 5433 <<'SQL'
CREATE ROLE daire LOGIN PASSWORD 'Kafuka2004!' CREATEDB;
CREATE DATABASE daire OWNER daire;
SQL
```

Kisha point backend kwake — `DAIRE/backend/.env`:

```env
DATABASE_URL=postgres://daire:<nenosiri>@127.0.0.1:5433/daire
```

Zindua migracji na thibitisha:

```bash
cd DAIRE/backend
python manage.py migrate
python manage.py shell -c "from django.db import connection; c=connection.cursor(); c.execute('SELECT current_database(), current_user'); print(c.fetchone())"
# -> ('daire', 'daire')
```

**Mtandao wa walipa:** database inaruhusu benki mbili tu — **NMB (`LDR-NMB-02`)** na **CRDB (`LDR-CRDB-01`)**. Walipa wa kale (Equity, Tigo, Airtel, Mwanga) huondolewa na data zao kwa:

```bash
python manage.py prune_lenders          # dry run
python manage.py prune_lenders --yes    # futa kweli
```

### 1.2 Backend + frontend ya Central System

```bash
# Backend (Django, port 8000)
cd DAIRE/backend && python manage.py runserver

# Frontend (Angular, port 4200) — terminal ya pili
cd DAIRE/frontend && npm start
```

> `python manage.py test core` inatengeneza test database ya muda — ndiyo sababu role ya `daire` inahitaji `CREATEDB`.

Kama Node haipo:

```bash
# Ubuntu / Debian
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Thibitisha
node -v && npm -v
```

**Kumbuka:** Ukiona hitilafu ya `EACCES` unapo-install global packages, usitumie `sudo npm`. Badala yake weka prefix ya npm kwenye home yako:

```bash
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

---

## 2. Install remixd

`remixd` ni daemon ndogo inayoshiriki folder yako na Remix IDE kupitia WebSocket ya ndani.

```bash
npm install -g @remix-project/remixd
```

Thibitisha:

```bash
remixd --version
```

### Jinsi remixd inavyofanya kazi

```
Remix IDE (browser)  <---- WebSocket kwenye port 65520 ---->  remixd (terminal yako)
                                                                    |
                                                                    v
                                                    ~/Documents/daire-contracts
```

Remix haipakii files zako kwenye internet. Inaunganisha **localhost** yako pekee.

> **Onyo la usalama (kutoka nyaraka rasmi za Remix):** remixd inatoa ruhusa kamili ya *kusoma na kuandika* kwenye folder uliyoishiriki, kwa programu yoyote inayoweza kufikia port 65520 kwenye localhost yako. Hakikisha port hii haijafunguliwa kwenye network yako, na simamisha remixd (`Ctrl + C`) ukimaliza kufanya kazi.

---

## 3. MetaMask, Sepolia na faucet

### 3.1 Weka MetaMask

1. Nenda [metamask.io](https://metamask.io) → install extension ya browser yako
2. Tengeneza wallet mpya
3. **Hifadhi seed phrase mahali salama nje ya computer.** Usiiweke kwenye folder ya project, kwenye Git, wala kwenye screenshot.

> Kwa kazi ya masomo, tumia wallet **mpya kabisa** isiyo na fedha halisi. Usitumie wallet yako binafsi.

### 3.2 Washa Sepolia network

MetaMask kwa default inaficha test networks:

1. Fungua MetaMask → menyu ya juu-kushoto ya network
2. Washa **"Show test networks"** (kwenye Settings → Advanced kama haionekani)
3. Chagua **Sepolia**

### 3.3 Pata Sepolia ETH bure

Utahitaji ETH ya Sepolia kulipia gas. Haina thamani halisi. Chaguo kadhaa:

| Faucet | Kiungo | Kumbuka |
|---|---|---|
| Google Cloud Web3 | https://cloud.google.com/application/web3/faucet/ethereum/sepolia | Inahitaji Google account |
| Alchemy | https://www.alchemy.com/faucets/ethereum-sepolia | Inahitaji akaunti ya Alchemy |
| QuickNode | https://faucet.quicknode.com/ethereum/sepolia | |
| GetBlock | https://getblock.io/faucet/eth-sepolia/ | |

Nakili anwani yako ya MetaMask (inaanza na `0x...`), bandika kwenye faucet, omba.

**0.05 ETH inatosha kabisa** kwa hatua hii yote. Faucets nyingi zina kikomo cha ombi moja kwa masaa 24, hivyo omba mapema.

Thibitisha: MetaMask ionyeshe salio kubwa kuliko sifuri kwenye Sepolia.

---

## 4. Washa remixd

Kutoka **ndani ya folder ya project**:

```bash
cd ~/Documents/daire-contracts
npm run remixd
```

Au moja kwa moja:

```bash
remixd -s ~/Documents/daire-contracts --remix-ide https://app.remix.live
```

Utaona kitu kama:

```
[WARN] You may now only use IDE at https://app.remix.live to connect to that instance
[INFO] Shared folder: /home/<wewe>/Documents/daire-contracts
[INFO] Sharing folder on port 65520
```

**Acha terminal hii ikiendelea kufanya kazi.** Ukifunga, muunganisho unakatika. Fungua terminal ya pili kwa amri nyingine (VS Code: `Ctrl + Shift + \``).

---

## 5. Unganisha Remix na localhost

1. Fungua **https://app.remix.live** kwenye browser
   *(`remix.ethereum.org` inaelekeza hapo hapo; tumia `app.remix.live` moja kwa moja ili kuepuka matatizo ya origin)*
2. Bonyeza icon ya **File Explorer** (juu-kushoto)
3. Bonyeza dropdown ya workspace → chagua **`- connect to localhost -`**
4. Modal itatokea ikikuonya kuhusu ruhusa → bonyeza **Connect**
5. Folder yako itatokea kama workspace ya **localhost**

Sasa fungua `contracts/DaireHandshake.sol` ndani ya Remix.

### Jaribio la muhimu

Badilisha kitu kwenye **VS Code** — mfano neno moja kwenye comment — kisha hifadhi. Angalia Remix: mabadiliko yanapaswa kuonekana **mara moja**. Hii inathibitisha kwamba unaandika mahali pamoja, siyo nakala mbili.

---

## 6. Compile

1. Bonyeza icon ya **Solidity Compiler** (upande wa kushoto)
2. Compiler version: chagua **0.8.24** au juu zaidi
3. Bonyeza **Compile DaireHandshake.sol**

Unachotarajia: alama ya kijani ya ✓ juu ya icon.

Ukiona makosa, soma jedwali la §10 hapa chini.

**Washa auto-compile** (checkbox) ili kila unapohifadhi kwenye VS Code, Remix i-compile yenyewe.

---

## 7. Deploy kwenye Sepolia

1. Bonyeza icon ya **Deploy & Run Transactions**
2. **ENVIRONMENT** → chagua **"Injected Provider - MetaMask"**
   *(SIYO "Remix VM" — hiyo ni simulation ya browser, haitaonekana Etherscan)*
3. MetaMask itafunguka ikiomba muunganisho → **Connect**
4. Thibitisha juu ya panel:
   - Network: **Sepolia (11155111)**
   - ACCOUNT: anwani yako yenye salio
5. **CONTRACT** → chagua `DaireHandshake`
6. Bonyeza **Deploy** (rangi ya machungwa)
7. MetaMask itaonyesha makadirio ya gas → **Confirm**

Subiri sekunde 15–30. Contract itatokea chini kwenye **Deployed Contracts**.

**Nakili anwani ya contract** (icon ya kunakili karibu na jina) — utaihitaji.

---

## 8. Interact na uone kwenye Etherscan

### 8.1 Soma (bure)

Panua contract kwenye Remix. Bonyeza buttons za **buluu**:

| Function | Kinachotarajiwa |
|---|---|
| `SYSTEM` | `DAIRE - Decentralized AI Reputation Engine` |
| `STAGE` | `Step 1 - handshake / pipeline verification` |
| `deployer` | Anwani yako ya MetaMask |
| `deployedAt` | Unix timestamp |
| `pingCount` | `0` |
| `info` | Vyote kwa pamoja |
| `ageInSeconds` | Inaongezeka kila unapobonyeza |

Hakuna MetaMask popup. Hakuna gas. Hii ni kusoma tu.

### 8.2 Andika (inagharimu gas)

1. Tafuta function ya **machungwa** ya `ping`
2. Kwenye field ya `note` andika: `"handshake test 1"` — **pamoja na alama za nukuu**
3. Bonyeza **transact**
4. MetaMask → **Confirm**
5. Subiri uthibitisho

Sasa bonyeza `pingCount` tena → itakuwa **1**. Umebadilisha hali ya blockchain.

### 8.3 Ona kwenye Sepolia Etherscan

Nenda **https://sepolia.etherscan.io** kisha bandika anwani ya contract yako kwenye search.

Utaona:

| Tab | Kinachoonekana |
|---|---|
| **Transactions** | Deployment tx pamoja na `ping` tx |
| **Internal Txns** | Tupu — contract hii haiiti nyingine |
| **Contract** | Bytecode (source haijathibitishwa bado) |
| **Events / Logs** | `Deployed` na `Ping` — hapa ndipo `note` yako ilipo |

Bonyeza transaction ya `ping` → shuka chini hadi **Logs** → utaona `newCount = 1` na ujumbe wako. **Hii ndiyo ledger.** Data yako iko kwenye Ethereum, haiwezi kubadilishwa na mtu yeyote.

---

## 9. Rekodi matokeo yako

Jaza jedwali hili — utahitaji taarifa hizi kwenye tasnifu na kwenye Step 2:

| Kitu | Thamani |
|---|---|
| Anwani ya wallet (Sepolia) | `0x...` |
| Anwani ya contract | `0x...` |
| Deployment tx hash | `0x...` |
| Block number | |
| Gas iliyotumika (deployment) | |
| Gas iliyotumika (`ping`) | |
| Tarehe na saa | |
| Kiungo cha Etherscan | `https://sepolia.etherscan.io/address/0x...` |

> Piga **screenshot** ya ukurasa wa Etherscan. Ni ushahidi mzuri wa kuweka kwenye tasnifu na kumwonyesha supervisor.

---

## 10. Troubleshooting

| Tatizo | Chanzo | Suluhisho |
|---|---|---|
| Remix: "Cannot connect to localhost" | remixd haiendeshi, au origin si sahihi | Hakikisha terminal ya remixd inaendelea. Tumia `https://app.remix.live` haswa |
| `remixd: command not found` | npm global bin haiko kwenye PATH | Angalia §1 (npm prefix) |
| Port 65520 already in use | remixd nyingine inaendelea | `pkill -f remixd` kisha anza upya |
| "Injected Provider" haionekani | MetaMask haijawekwa au browser haijaonyeshwa | Refresh ukurasa baada ya ku-install MetaMask |
| MetaMask inaonyesha network isiyo sahihi | Umechagua Mainnet | Badilisha kuwa Sepolia kabla ya kubonyeza Deploy |
| "insufficient funds for gas" | Hakuna Sepolia ETH | Rudi kwenye faucet (§3.3) |
| Compiler error: pragma mismatch | Version ya compiler ni ndogo | Chagua 0.8.24 au juu |
| Transaction inakaa "pending" milele | Gas price ndogo mno | MetaMask → Speed up, au Settings → Advanced → Clear activity tab data |
| Files hazionekani Remix | Umeshiriki folder isiyo sahihi | Hakikisha `-s` inaelekeza `~/Documents/daire-contracts` |
| Mabadiliko ya VS Code hayaonekani Remix | Muunganisho umekatika | Unganisha upya kupitia dropdown ya workspace |

---

## 11. Checklist ya kumaliza Step 1

- [ ] `node -v` na `npm -v` zinafanya kazi
- [ ] `remixd --version` inafanya kazi
- [ ] MetaMask imewekwa, Sepolia imewashwa
- [ ] Salio la Sepolia ETH ni kubwa kuliko sifuri
- [ ] remixd inaendelea, folder imeshirikiwa
- [ ] Remix imeunganishwa na localhost, files zinaonekana
- [ ] Mabadiliko ya VS Code yanaonekana Remix mara moja
- [ ] `DaireHandshake.sol` ime-compile bila makosa
- [ ] Ime-deploy kwenye Sepolia kupitia Injected Provider
- [ ] Read functions zinarudisha thamani sahihi
- [ ] `ping()` imefanikiwa, `pingCount` ni 1
- [ ] Contract inaonekana kwenye Sepolia Etherscan
- [ ] Event ya `Ping` inaonekana kwenye tab ya Logs
- [ ] Jedwali la §9 limejazwa
- [ ] Screenshot imepigwa

Ukikamilisha vyote — **niambie**, na tunaingia Step 2.

---

## 12. Kinachofuata — Step 2

`contracts/DaireCreditScore.sol`:

- `struct BorrowerFeatures` — features za mkopaji zinazotumwa na Central System
- `submitFeatures()` — Hub inatuma data, ikilindwa na access control
- `calculateScore()` — **hesabu ya D1–D5 na score 300–850 (kiwango cha US) ndani ya contract**
- Storage ya score na historia yake kwenye ledger
- Events kwa ajili ya API kusikiliza
- `getScore()` — read function ambayo API yetu itaiita

Soma `docs/ARCHITECTURE.md` sasa ili uelewe data zinatoka wapi kabla ya kufika kwenye contract.
