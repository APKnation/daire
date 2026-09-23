import fs from "node:fs";
import path from "node:path";
import hre from "hardhat";

async function main() {
  console.log("Deploying DaireCreditScore to local Hardhat node...");

  const { ethers, networkName } = await hre.network.getOrCreate();
  console.log(`Network: ${networkName}`);

  const [deployer] = await ethers.getSigners();
  console.log(`Deploying with account: ${deployer.address}`);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`Account balance: ${ethers.formatEther(balance)} ETH`);

  const daireContract = await ethers.deployContract("DaireCreditScore");
  await daireContract.waitForDeployment();

  const contractAddress = await daireContract.getAddress();
  console.log("\n==================================================");
  console.log(`DaireCreditScore deployed to: ${contractAddress}`);
  console.log("==================================================\n");

  // Andika CONTRACT_ADDRESS kwenye profile ya local ya middleware, ili
  // `npm run start:local` ianze bila kuhariri chochote.
  const envPath = path.join(process.cwd(), "daire-middleware", ".env.local");
  if (fs.existsSync(envPath) && networkName === "localhost") {
    let env = fs.readFileSync(envPath, "utf8");
    const re = /^CONTRACT_ADDRESS=.*$/m;
    const line = `CONTRACT_ADDRESS=${contractAddress}`;
    env = re.test(env) ? env.replace(re, line) : `${env}\n${line}\n`;
    fs.writeFileSync(envPath, env);
    console.log(`[OK] CONTRACT_ADDRESS written to daire-middleware/.env.local`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
