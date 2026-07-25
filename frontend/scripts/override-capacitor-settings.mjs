import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, "..");
const settingsPath = path.join(frontendDir, "android", "capacitor.settings.gradle");

const original = readFileSync(settingsPath, "utf8");
const expected = "project(':exxili-capacitor-nfc').projectDir = new File('../node_modules/@exxili/capacitor-nfc/android')";
const replacement = "project(':exxili-capacitor-nfc').projectDir = new File('../android-plugins/exxili-capacitor-nfc/android')";

if (!original.includes(expected) && original.includes(replacement)) {
  console.log("Capacitor settings already point at the local NFC plugin override.");
  process.exit(0);
}

if (!original.includes(expected)) {
  throw new Error(`Could not find the generated Exxili NFC plugin path in ${settingsPath}`);
}

writeFileSync(settingsPath, original.replace(expected, replacement), "utf8");
console.log("Rewired capacitor.settings.gradle to the local NFC plugin override.");
