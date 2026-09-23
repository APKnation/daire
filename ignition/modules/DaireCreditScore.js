import { buildModule } from "@nomicfoundation/ignition-core";

/**
 * DAIRE — DaireCreditScore deployment module.
 * Deployer becomes owner + first authorized Hub (constructor behaviour).
 */
const DaireCreditScoreModule = buildModule("DaireCreditScoreModule", (m) => {
  const daireCreditScore = m.contract("DaireCreditScore");

  return { daireCreditScore };
});

export default DaireCreditScoreModule;
