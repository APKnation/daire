# Deployments

Rekodi ya kila contract iliyo-deploy. Jaza baada ya kila deployment.

## Sepolia (chainId 11155111)

| Contract | Address | Tx hash | Block | Date | Notes |
|---|---|---|---|---|---|
| DaireHandshake | `0x...` | `0x...` | | | Step 1 — pipeline test |
| DaireCreditScore | `0x6f57098c3b5d0120cc4f1337974e7c14be9c44b0` | `0x21baf9419058b3c0983094b8f4448c152ee81ab73a7cc8a026c2a88cf8ec6f0e` | 11682388 | 2026-09-11 | Step 2 — RULESET 2.0 US-RANGE (300–850). Gas 3,922,043, fee ~0.0101 ETH. Deployer: `0xaa5dbA90D8D0279B4a350193AF53d358D26bfFef` |

### Baada ya deployment

- [ ] Source verification kwenye Etherscan (compiler 0.8.24, bila optimization kama Remix ilivyotumia) — haitajwa bado
- [ ] `previewScore` na test vector A imethibitishwa kwa contract ya Sepolia (score 796)

Etherscan: https://sepolia.etherscan.io/address/0x6f57098c3b5d0120cc4f1337974e7c14be9c44b0

## Usiweke hapa

Private keys, seed phrases, au API keys. Anwani za umma na tx hashes pekee.
