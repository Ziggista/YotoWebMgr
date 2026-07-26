#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const frontendDir = resolve(scriptDir, "..");
const repoDir = resolve(frontendDir, "..");
const packageJsonPath = resolve(frontendDir, "package.json");

function gitOutput(args, fallback) {
  try {
    return execFileSync("git", ["-C", repoDir, ...args], { encoding: "utf8" }).trim();
  } catch {
    return fallback;
  }
}

function parseBuildNumber(rawValue) {
  const value = Number.parseInt(String(rawValue ?? ""), 10);
  return Number.isFinite(value) && value > 0 ? value : null;
}

function padBuildNumber(buildNumber) {
  return String(buildNumber).padStart(4, "0");
}

function loadVersionMeta() {
  const packageJson = JSON.parse(readFileSync(packageJsonPath, "utf8"));
  const baseVersion = String(packageJson.version ?? "0.1.0");
  const [major = "0", minor = "1"] = baseVersion.split(".");
  const requestedBuildNumber =
    parseBuildNumber(process.env.APP_BUILD_NUMBER) ??
    parseBuildNumber(process.env.VITE_APP_BUILD_NUMBER) ??
    parseBuildNumber(gitOutput(["rev-list", "--count", "HEAD"], "1")) ??
    1;
  const buildSha = (
    process.env.VITE_APP_BUILD_SHA ??
    process.env.APP_BUILD_SHA ??
    gitOutput(["rev-parse", "--short", "HEAD"], "dev")
  ).trim();
  const versionCode = requestedBuildNumber;
  const versionName = `v${major}.${minor}b${padBuildNumber(requestedBuildNumber)}`;
  return {
    baseVersion,
    marketingVersion: `${major}.${minor}`,
    buildNumber: requestedBuildNumber,
    buildNumberPadded: padBuildNumber(requestedBuildNumber),
    versionCode,
    versionName,
    buildSha,
    otaVersion: `${versionName}+${buildSha}`,
  };
}

const args = process.argv.slice(2);
const meta = loadVersionMeta();

if (args[0] === "--field" && args[1]) {
  const value = meta[args[1]];
  if (value === undefined) {
    process.exitCode = 1;
  } else if (typeof value === "object") {
    process.stdout.write(`${JSON.stringify(value)}\n`);
  } else {
    process.stdout.write(`${String(value)}\n`);
  }
} else {
  process.stdout.write(`${JSON.stringify(meta, null, 2)}\n`);
}
