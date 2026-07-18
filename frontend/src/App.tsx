import { FormEvent, useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useParams } from "react-router-dom";
import AudioPlayer from "react-h5-audio-player";
import "react-h5-audio-player/lib/styles.css";
import { Capacitor } from "@capacitor/core";
import { CapacitorUpdater } from "@capgo/capacitor-updater";
import { NFC, type NDEFMessagesTransformable } from "@exxili/capacitor-nfc";
import {
  AppSettings,
  AuthProvidersResponse,
  BuildInfo,
  CardAssignmentEvent,
  CardScanDumpEntry,
  CardPlan,
  CreateLiveYotoPlaylistResponse,
  ImportSourceInfo,
  ImportRequest,
  Job,
  LibraryItemDetail,
  LibraryItem,
  PhysicalCard,
  ReadinessResponse,
  SessionResponse,
  Tag,
  VersionEvent,
  YotoApiDebugResponse,
  YotoCredentialProbeResponse,
  YotoCredentialStatus,
  YotoPlaylistDraft,
  YotoPlaylistRemotePayload,
  YotoPlaylistVersion,
  applyTrackIcon,
  approveImportReview,
  createCard,
  createLiveYotoPlaylist,
  createImport,
  createTag,
  createPodcastFeed,
  createRadioStreamTrack,
  createSplitPoint,
  completeYotoOAuth,
  debugYotoApiRequest,
  disconnectYotoCredentials,
  dumpCardScan,
  fetchBackendBuildInfo,
  fetchCard,
  fetchCardHistory,
  fetchCardScanDumps,
  fetchCards,
  fetchCardPlan,
  fetchImportSources,
  fetchImports,
  fetchJobs,
  fetchLibraryItemDetail,
  fetchLibraryItems,
  fetchLibraryItemVersions,
  fetchReadiness,
  fetchSavedCardPlan,
  fetchSettings,
  fetchTags,
  fetchYotoCredentialStatus,
  fetchYotoPlaylists,
  fetchYotoPlaylistRemotePayload,
  fetchYotoPlaylistVersions,
  hideImport,
  fetchAuthProviders,
  linkLibraryItemToCard,
  loginWithPassword,
  quickSelectUser,
  queueArtworkPixelise,
  queueLibraryItemProcessing,
  probeYotoCredentials,
  queueYotoPlaylist,
  restoreLibraryItemVersion,
  restoreYotoPlaylistVersion,
  retryJob,
  saveCardPlan,
  setLibraryItemTags,
  startYotoOAuth,
  updateYotoPlaylistRemoteLink,
  updatePlaylistTrack,
  updateLibraryItemSettings,
  updateCard,
  updateSettings,
  uploadCoverArt,
  uploadImport,
  updateImportReview,
} from "./api";
import { resolveAndroidUpdateManifestUrl } from "./api-config";
import "./App.css";

const sections = ["Library", "Import", "Cards", "Jobs", "Tags", "Settings"];
const sessionStorageKey = "yotowebmgr.session";
const contentTypes = [
  "Audiobook",
  "Music Album",
  "Story Collection",
  "Podcast",
  "Radio Play",
  "Sleep Sounds",
  "Custom Playlist",
  "Other Audio",
];
const defaultNdefFormatCommand = "A2:03:E1:10:06:00,A2:04:03:04:D8:00,A2:05:00:00:FE:00";
const yotoPkceStorageKey = "yotowebmgr.yoto.pkce";
const yotoPkceExchangeKey = "yotowebmgr.yoto.pkce.exchange";
const frontendBuildSha = import.meta.env.VITE_APP_BUILD_SHA ?? "dev";
const stagedCardDumpStorageKey = "yotowebmgr.cards.stagedDump";
const yotoDebugPresets = [
  { label: "MYO content", method: "GET" as const, path: "/content/mine?showdeleted=false" },
  { label: "Family library groups", method: "GET" as const, path: "/card/family/library/groups" },
  { label: "Devices", method: "GET" as const, path: "/device-v2/devices/mine" },
  { label: "Family view", method: "GET" as const, path: "/family/mine" },
  { label: "Family images", method: "GET" as const, path: "/media/family/images" },
];

type WorkflowStep = {
  key: string;
  label: string;
  done: boolean;
  detail: string;
};

type AndroidUpdateManifest = {
  version: string;
  build_sha: string;
  app_version: string;
  bundle_url: string;
  generated_at: string;
  notes?: string;
};

type AndroidUpdateState =
  | {
      kind: "unavailable";
      detail: string;
    }
  | {
      kind: "idle";
      detail: string;
      currentVersion: string | null;
      nativeVersion: string | null;
    }
  | {
      kind: "checking";
      detail: string;
      currentVersion: string | null;
      nativeVersion: string | null;
    }
  | {
      kind: "up_to_date";
      detail: string;
      currentVersion: string | null;
      nativeVersion: string | null;
      remoteVersion: string;
    }
  | {
      kind: "blocked";
      detail: string;
      currentVersion: string | null;
      nativeVersion: string | null;
      remoteVersion: string;
    }
  | {
      kind: "downloading";
      detail: string;
      currentVersion: string | null;
      nativeVersion: string | null;
      remoteVersion: string;
      percent: number;
    }
  | {
      kind: "ready";
      detail: string;
      currentVersion: string | null;
      nativeVersion: string | null;
      remoteVersion: string;
      bundleId: string;
    }
  | {
      kind: "error";
      detail: string;
      currentVersion: string | null;
      nativeVersion: string | null;
    };

type NdefRecordWithData = {
  data?: ArrayBuffer | DataView | Uint8Array | null;
};

type NdefReadingEvent = Event & {
  serialNumber?: string;
  message: {
    records: NdefRecordWithData[];
  };
};

function isWebNfcAvailable(): boolean {
  return typeof window !== "undefined" && "NDEFReader" in window;
}

function isAndroidAppRuntime(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  const { hostname, protocol } = window.location;
  return hostname === "localhost" && (protocol === "http:" || protocol === "https:" || protocol === "capacitor:");
}

function isNativeAndroidRuntime(): boolean {
  return Capacitor.getPlatform() === "android" && isAndroidAppRuntime();
}

function formatNfcScanError(error: unknown): string {
  if (!(error instanceof Error)) {
    return "Could not start NFC scan.";
  }

  if (error.name === "NotAllowedError") {
    return isAndroidAppRuntime()
      ? "NFC permission was denied by the Android app WebView. Tap Request NFC permission once, then try Scan with phone again. If Android still denies it, use Chrome or NFC Tools for capture."
      : "NFC permission was denied. Allow NFC access for this page, then try again.";
  }

  if (error.name === "NotSupportedError") {
    return "This runtime does not support Web NFC. Use Chrome on Android or capture the card with NFC Tools.";
  }

  return error.message || "Could not start NFC scan.";
}

function normaliseRecordData(data: ArrayBuffer | DataView | Uint8Array): Uint8Array {
  if (data instanceof Uint8Array) {
    return data;
  }
  if (data instanceof DataView) {
    return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
  }
  return new Uint8Array(data);
}

function decodeNdefRecords(records: NdefRecordWithData[]): { text: string | null; hex: string | null } {
  const recordBytes = records
    .map((record) => record.data)
    .filter((data): data is ArrayBuffer | DataView | Uint8Array => Boolean(data))
    .map(normaliseRecordData);

  if (recordBytes.length === 0) {
    return { text: null, hex: null };
  }

  const text = recordBytes
    .map((bytes) => new TextDecoder().decode(bytes).trim())
    .filter(Boolean)
    .join(" | ");
  const hex = recordBytes
    .map((bytes) =>
      Array.from(bytes)
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join(""),
    )
    .join(" ");

  return {
    text: text || null,
    hex: hex || null,
  };
}

function textToHex(value: string): string {
  return Array.from(new TextEncoder().encode(value))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function hexToBytes(value: string): Uint8Array | null {
  const normalized = value.replace(/[^0-9a-f]/gi, "");
  if (!normalized || normalized.length % 2 !== 0) {
    return null;
  }

  const bytes = new Uint8Array(normalized.length / 2);
  for (let index = 0; index < normalized.length; index += 2) {
    bytes[index / 2] = Number.parseInt(normalized.slice(index, index + 2), 16);
  }
  return bytes;
}

function playlistIdFromUri(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const match = trimmed.match(/\/playlist\/([^/?#]+)/i);
  if (match?.[1]) {
    return match[1];
  }
  return null;
}

function generatedCardPayload(playlistUri: string): {
  programmableId: string | null;
  payloadText: string | null;
  payloadHex: string | null;
} {
  const trimmedUri = playlistUri.trim();
  if (!trimmedUri) {
    return { programmableId: null, payloadText: null, payloadHex: null };
  }
  const playlistId = playlistIdFromUri(trimmedUri);
  return {
    programmableId: playlistId ? `yoto:playlist:${playlistId}` : trimmedUri,
    payloadText: trimmedUri,
    payloadHex: textToHex(trimmedUri),
  };
}

function yotoDraftChapterCount(payload: Record<string, unknown>): number {
  const directChapters = payload.chapters;
  if (Array.isArray(directChapters)) {
    return directChapters.length;
  }
  const content = payload.content;
  if (content && typeof content === "object" && !Array.isArray(content)) {
    const nestedChapters = (content as { chapters?: unknown }).chapters;
    if (Array.isArray(nestedChapters)) {
      return nestedChapters.length;
    }
  }
  return 0;
}

function currentRuntimeLabel(): string {
  if (isNativeAndroidRuntime()) {
    return "capacitor_android";
  }
  if (isAndroidAppRuntime()) {
    return "android_webview";
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname || "browser"}`;
  }
  return "unknown";
}

async function copyToClipboard(value: string): Promise<boolean> {
  if (!value || typeof navigator === "undefined" || !navigator.clipboard) {
    return false;
  }
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

async function fetchAndroidUpdateManifest(): Promise<AndroidUpdateManifest> {
  const manifestUrl = resolveAndroidUpdateManifestUrl();
  if (!manifestUrl) {
    throw new Error("No Android update host is configured yet.");
  }
  const response = await fetch(`${manifestUrl}?t=${Date.now()}`);
  if (!response.ok) {
    throw new Error(`Update manifest request failed with HTTP ${response.status}.`);
  }
  return response.json() as Promise<AndroidUpdateManifest>;
}

function cardWorkflowSteps(card: PhysicalCard | null): WorkflowStep[] {
  const readSummary = card?.nfc_serial_number ?? card?.programmable_id ?? card?.ndef_payload_text;
  return [
    {
      key: "scan",
      label: "Read card",
      done: Boolean(readSummary),
      detail: readSummary ?? "Capture the NFC serial or copied playlist payload.",
    },
    {
      key: "prepare",
      label: "Prepare NDEF",
      done: Boolean(card?.ndef_prepared),
      detail: card?.ndef_format_command ?? "Use the recorded NFC Tools format command.",
    },
    {
      key: "link",
      label: "Link playlist",
      done: Boolean(card?.linked_manually || card?.ready_to_link_in_app),
      detail: card?.yoto_playlist_uri ?? "Create the playlist, then link it through the Yoto app.",
    },
    {
      key: "download",
      label: "Download to player",
      done: Boolean(card?.downloaded_to_player_confirmed),
      detail: card?.needs_player_download ? "Still needs a player download check." : "Record the download check.",
    },
    {
      key: "test",
      label: "Test playback",
      done: Boolean(card?.tested),
      detail: card?.notes ?? "Tap the card on the player and record the result.",
    },
  ];
}

function latestJobForItem(jobs: Job[], type: string): Job | null {
  return jobs
    .filter((job) => job.type === type)
    .sort((left, right) => right.id - left.id)[0] ?? null;
}

function latestYotoPlaylist(playlists: YotoPlaylistDraft[]): YotoPlaylistDraft | null {
  return [...playlists].sort((left, right) => right.id - left.id)[0] ?? null;
}

function yotoPlaylistWorkflowSteps(
  detail: LibraryItemDetail,
  jobs: Job[],
  playlists: YotoPlaylistDraft[],
): WorkflowStep[] {
  const processingJob = latestJobForItem(jobs, "transcode_audio");
  const playlistJob = latestJobForItem(jobs, "create_yoto_playlist");
  const playlist = latestYotoPlaylist(playlists);
  const processed = detail.processed_assets.length > 0;
  const localDraftReady = Boolean(playlist);
  const remoteCreated = Boolean(
    playlist &&
      (playlist.status === "remote_created" ||
        playlist.status === "remote_linked" ||
        playlist.remote_playlist_id ||
        playlist.remote_playlist_uri),
  );
  const readyForCards = Boolean(playlist?.remote_playlist_uri || playlist?.remote_playlist_id);

  return [
    {
      key: "processed",
      label: "Audio processed",
      done: processed,
      detail: processed
        ? `Generated ${detail.processed_assets.length} Yoto-ready asset(s).`
        : processingJob
          ? `${processingJob.status} · ${processingJob.progress_percent}% · ${processingJob.progress_message}`
          : "Run Process audio to create Yoto-ready files first.",
    },
    {
      key: "draft",
      label: "Local playlist draft",
      done: localDraftReady,
      detail: localDraftReady
        ? `Draft #${playlist?.id ?? "?"} is ${playlist?.status ?? "queued"} with ${yotoDraftChapterCount(
            playlist?.payload ?? {},
          )} track(s).`
        : playlistJob
          ? `${playlistJob.status} · ${playlistJob.progress_percent}% · ${playlistJob.progress_message}`
          : "Queue Yoto playlist to build the local payload and draft.",
    },
    {
      key: "cloud",
      label: "Yoto cloud content",
      done: remoteCreated,
      detail: remoteCreated
        ? `Created in Yoto cloud as ${playlist?.remote_playlist_uri ?? playlist?.remote_playlist_id}.`
        : playlist?.last_error
          ? `Last cloud error: ${playlist.last_error}`
          : localDraftReady
            ? "Use Create live playlist and link cards, then wait for the remote playlist ID or URI."
            : "Cloud create starts after the local draft exists.",
    },
    {
      key: "cards",
      label: "Ready for card write/link",
      done: readyForCards,
      detail: readyForCards
        ? "The Yoto playlist exists remotely. Go to Cards to write the payload to a blank card or mark an existing card linked."
        : "Card programming stays blocked until the remote playlist ID or URI is recorded here.",
    },
  ];
}

function workflowStatusSummary(steps: WorkflowStep[]): { title: string; detail: string } {
  const nextStep = steps.find((step) => !step.done);
  if (!nextStep) {
    return {
      title: "Workflow complete",
      detail: "The known steps are complete. Final verification now happens on the physical card and player.",
    };
  }
  return {
    title: `Current stage: ${nextStep.label}`,
    detail: nextStep.detail,
  };
}

function PlaceholderPage({ title }: { title: string }) {
  return (
    <section className="panel">
      <p className="eyebrow">Milestone 1</p>
      <h2>{title}</h2>
      <p>
        This area is scaffolded and ready for feature work. The initial focus is authentication,
        library data, job orchestration, and import flows.
      </p>
    </section>
  );
}

function EmptyState({ message }: { message: string }) {
  return <p className="muted">{message}</p>;
}

function BackendUnavailablePanel({
  error,
  onRetry,
}: {
  error: string;
  onRetry: () => void;
}) {
  return (
    <section className="auth-panel backend-unavailable-panel">
      <p className="eyebrow">Backend unavailable</p>
      <h2>Connect to the backend to continue</h2>
      <p className="auth-copy">
        The app could not reach the YotoWebMgr backend. Connect this device to the same Tailscale
        network and confirm the backend is reachable before continuing.
      </p>
      <div className="settings-connection-panel">
        <p className="settings-note">
          Expected backend host: <strong>http://ziggi-pc-1.tailaf3d4b.ts.net:5175</strong>
        </p>
        <p className="auth-error">{error}</p>
        <div className="button-row">
          <button className="primary-button" onClick={onRetry} type="button">
            Retry connection
          </button>
          <a className="secondary-button" href="http://ziggi-pc-1.tailaf3d4b.ts.net:5175">
            Open backend host
          </a>
        </div>
      </div>
    </section>
  );
}

function YotoJsonTree({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value === null) {
    return <span className="json-primitive">null</span>;
  }
  if (typeof value === "string") {
    return <span className="json-string">"{value}"</span>;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return <span className="json-primitive">{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="json-empty">[]</span>;
    }
    return (
      <div className="json-tree">
        {value.map((entry, index) => (
          <details className="json-node" key={`${depth}-array-${index}`} open={depth < 1}>
            <summary>
              <span className="json-key">[{index}]</span>
            </summary>
            <div className="json-child">
              <YotoJsonTree depth={depth + 1} value={entry} />
            </div>
          </details>
        ))}
      </div>
    );
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) {
      return <span className="json-empty">{`{}`}</span>;
    }
    return (
      <div className="json-tree">
        {entries.map(([key, entry]) => (
          <details className="json-node" key={`${depth}-${key}`} open={depth < 1}>
            <summary>
              <span className="json-key">{key}</span>
            </summary>
            <div className="json-child">
              <YotoJsonTree depth={depth + 1} value={entry} />
            </div>
          </details>
        ))}
      </div>
    );
  }
  return <span className="json-primitive">{String(value)}</span>;
}

function WorkflowChecklist({ steps }: { steps: WorkflowStep[] }) {
  return (
    <div className="card-workflow-steps">
      {steps.map((step, index) => (
        <article className={`workflow-step${step.done ? " workflow-step-done" : ""}`} key={step.key}>
          <span className="workflow-step-number">{step.done ? "OK" : index + 1}</span>
          <div>
            <strong>{step.label}</strong>
            <p className="muted">{step.detail}</p>
          </div>
        </article>
      ))}
    </div>
  );
}

function CardWorkflowChecklist({ card }: { card: PhysicalCard | null }) {
  return <WorkflowChecklist steps={cardWorkflowSteps(card)} />;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "Unknown";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

function cardPlanAssignments(plan: CardPlan | null): Record<number, number> {
  const assignments: Record<number, number> = {};
  plan?.parts.forEach((part) => {
    part.tracks.forEach((track) => {
      assignments[track.track_id] = part.part_number;
    });
  });
  return assignments;
}

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return window
    .btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function sha256Fallback(bytes: Uint8Array): Uint8Array {
  const words: number[] = [];
  const bitLength = bytes.length * 8;
  for (let index = 0; index < bytes.length; index += 1) {
    words[index >> 2] = (words[index >> 2] || 0) | (bytes[index] << (24 - (index % 4) * 8));
  }
  words[bitLength >> 5] = (words[bitLength >> 5] || 0) | (0x80 << (24 - (bitLength % 32)));
  words[(((bitLength + 64) >> 9) << 4) + 15] = bitLength;

  const k = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ];
  const hash = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ];
  const schedule = new Array<number>(64);

  for (let blockStart = 0; blockStart < words.length; blockStart += 16) {
    for (let index = 0; index < 16; index += 1) {
      schedule[index] = words[blockStart + index] || 0;
    }
    for (let index = 16; index < 64; index += 1) {
      const s0Word = schedule[index - 15];
      const s1Word = schedule[index - 2];
      const s0 =
        ((s0Word >>> 7) | (s0Word << 25)) ^
        ((s0Word >>> 18) | (s0Word << 14)) ^
        (s0Word >>> 3);
      const s1 =
        ((s1Word >>> 17) | (s1Word << 15)) ^
        ((s1Word >>> 19) | (s1Word << 13)) ^
        (s1Word >>> 10);
      schedule[index] = (schedule[index - 16] + s0 + schedule[index - 7] + s1) | 0;
    }

    let [a, b, c, d, e, f, g, h] = hash;
    for (let index = 0; index < 64; index += 1) {
      const s1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      const choice = (e & f) ^ (~e & g);
      const temp1 = (h + s1 + choice + k[index] + schedule[index]) | 0;
      const s0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (s0 + majority) | 0;

      h = g;
      g = f;
      f = e;
      e = (d + temp1) | 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) | 0;
    }

    hash[0] = (hash[0] + a) | 0;
    hash[1] = (hash[1] + b) | 0;
    hash[2] = (hash[2] + c) | 0;
    hash[3] = (hash[3] + d) | 0;
    hash[4] = (hash[4] + e) | 0;
    hash[5] = (hash[5] + f) | 0;
    hash[6] = (hash[6] + g) | 0;
    hash[7] = (hash[7] + h) | 0;
  }

  const digest = new Uint8Array(32);
  hash.forEach((value, index) => {
    digest[index * 4] = (value >>> 24) & 0xff;
    digest[index * 4 + 1] = (value >>> 16) & 0xff;
    digest[index * 4 + 2] = (value >>> 8) & 0xff;
    digest[index * 4 + 3] = value & 0xff;
  });
  return digest;
}

async function sha256Bytes(bytes: Uint8Array): Promise<Uint8Array> {
  const webCrypto = globalThis.crypto;
  if (webCrypto?.subtle) {
    const digestInput = new Uint8Array(bytes.byteLength);
    digestInput.set(bytes);
    const digest = await webCrypto.subtle.digest("SHA-256", digestInput);
    return new Uint8Array(digest);
  }
  return sha256Fallback(bytes);
}

async function createPkcePair(): Promise<{ verifier: string; challenge: string }> {
  const verifierBytes = new Uint8Array(64);
  const webCrypto = globalThis.crypto;
  if (!webCrypto) {
    throw new Error("This browser runtime does not provide Web Crypto for PKCE generation.");
  }
  webCrypto.getRandomValues(verifierBytes);
  const verifier = base64UrlEncode(verifierBytes);
  const encodedVerifier = new TextEncoder().encode(verifier);
  const digest = await sha256Bytes(encodedVerifier);
  return {
    verifier,
    challenge: base64UrlEncode(digest),
  };
}

function LibraryPage() {
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [filters, setFilters] = useState({ search: "", content_type: "", tag_id: "" });
  const [cards, setCards] = useState<PhysicalCard[]>([]);
  const [activeLinkItemId, setActiveLinkItemId] = useState<number | null>(null);
  const [selectedCardId, setSelectedCardId] = useState("");
  const [detail, setDetail] = useState<LibraryItemDetail | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [coverArtPath, setCoverArtPath] = useState("");
  const [coverArtFile, setCoverArtFile] = useState<File | null>(null);
  const [trackIconPath, setTrackIconPath] = useState("");
  const [bulkTrackBehavior, setBulkTrackBehavior] = useState("continue");
  const [radioForm, setRadioForm] = useState({ title: "", stream_url: "", icon_path: "" });
  const [podcastForm, setPodcastForm] = useState({ title: "", rss_url: "" });
  const [splitForm, setSplitForm] = useState({ timestamp_seconds: "", title: "", part_number: "" });
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [linkMessage, setLinkMessage] = useState<string | null>(null);
  const [linking, setLinking] = useState(false);

  async function refreshLibraryList() {
    const nextItems = await fetchLibraryItems({
      search: filters.search.trim() || undefined,
      content_type: filters.content_type || undefined,
      tag_id: filters.tag_id ? Number(filters.tag_id) : null,
    });
    setItems(nextItems);
  }

  useEffect(() => {
    void Promise.all([refreshLibraryList(), fetchTags().then(setTags)])
      .then(() => undefined)
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "Failed to load library."),
      );
  }, [filters.search, filters.content_type, filters.tag_id]);

  async function openLinkPanel(itemId: number) {
    setError(null);
    setLinkMessage(null);
    setActiveLinkItemId(itemId);
    try {
      const nextCards = cards.length > 0 ? cards : await fetchCards();
      setCards(nextCards);
      setSelectedCardId(nextCards[0] ? String(nextCards[0].id) : "");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load cards.");
    }
  }

  async function openDetailPanel(itemId: number) {
    setError(null);
    setLinkMessage(null);
    setDetailLoading(true);
    try {
      const [nextDetail, nextReadiness] = await Promise.all([
        fetchLibraryItemDetail(itemId),
        fetchReadiness(itemId),
      ]);
      setDetail(nextDetail);
      setReadiness(nextReadiness);
      setCoverArtPath(nextDetail.item.cover_art_path ?? "");
      setCoverArtFile(null);
      setTrackIconPath("");
      setBulkTrackBehavior("continue");
      setSelectedTagIds(nextDetail.item.tags.map((tag) => tag.id));
      setRadioForm({ title: "", stream_url: "", icon_path: "" });
      setPodcastForm({ title: "", rss_url: "" });
      setSplitForm({ timestamp_seconds: "", title: "", part_number: "" });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load item detail.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function refreshDetail(itemId: number) {
    const [nextDetail, nextReadiness] = await Promise.all([
      fetchLibraryItemDetail(itemId),
      fetchReadiness(itemId),
    ]);
    setDetail(nextDetail);
    setReadiness(nextReadiness);
    setItems((current) =>
      current.map((item) => (item.id === nextDetail.item.id ? nextDetail.item : item)),
    );
    setSelectedTagIds(nextDetail.item.tags.map((tag) => tag.id));
  }

  async function handleSavePlaylistSettings() {
    if (!detail) return;
    setError(null);
    try {
      const updated = await updateLibraryItemSettings(detail.item.id, {
        cover_art_path: coverArtPath || null,
        playlist_always_play_from_start: detail.item.playlist_always_play_from_start,
        playlist_shuffle_tracks: detail.item.playlist_shuffle_tracks,
        playlist_hide_track_numbers: detail.item.playlist_hide_track_numbers,
      });
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      await refreshDetail(updated.id);
      setLinkMessage("Playlist settings saved.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save settings.");
    }
  }

  async function handleUploadCoverArt() {
    if (!detail || !coverArtFile) return;
    setError(null);
    try {
      const updated = await uploadCoverArt(detail.item.id, coverArtFile);
      setCoverArtPath(updated.cover_art_path ?? "");
      setCoverArtFile(null);
      await refreshDetail(updated.id);
      setLinkMessage("Cover artwork uploaded.");
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Failed to upload cover art.");
    }
  }

  function setDetailOption(
    key:
      | "playlist_always_play_from_start"
      | "playlist_shuffle_tracks"
      | "playlist_hide_track_numbers",
    value: boolean,
  ) {
    setDetail((current) =>
      current ? { ...current, item: { ...current.item, [key]: value } } : current,
    );
  }

  async function handleApplyIcon() {
    if (!detail || !trackIconPath) return;
    setError(null);
    try {
      await applyTrackIcon(detail.item.id, trackIconPath);
      await refreshDetail(detail.item.id);
      setLinkMessage("Track icon applied.");
    } catch (iconError) {
      setError(iconError instanceof Error ? iconError.message : "Failed to apply icon.");
    }
  }

  async function handleSaveTags() {
    if (!detail) return;
    setError(null);
    try {
      await setLibraryItemTags(detail.item.id, selectedTagIds);
      await Promise.all([refreshDetail(detail.item.id), refreshLibraryList(), fetchTags().then(setTags)]);
      setLinkMessage("Tags saved.");
    } catch (tagError) {
      setError(tagError instanceof Error ? tagError.message : "Failed to save tags.");
    }
  }

  async function handleUpdateTrack(event: FormEvent<HTMLFormElement>, trackId: number) {
    event.preventDefault();
    if (!detail) return;
    const formData = new FormData(event.currentTarget);
    const durationValue = String(formData.get("duration_seconds") ?? "");
    const startValue = String(formData.get("source_start_seconds") ?? "");
    const endValue = String(formData.get("source_end_seconds") ?? "");
    const sourceUrl = String(formData.get("source_url") ?? "").trim();
    const streamUrl = String(formData.get("stream_url") ?? "").trim();

    setError(null);
    try {
      await updatePlaylistTrack(detail.item.id, trackId, {
        title: String(formData.get("title") ?? ""),
        source_url: sourceUrl || null,
        source_start_seconds: startValue ? Number(startValue) : null,
        source_end_seconds: endValue ? Number(endValue) : null,
        track_number: Number(formData.get("track_number") ?? 1),
        duration_seconds: durationValue ? Number(durationValue) : null,
        icon_path: String(formData.get("icon_path") ?? "").trim() || null,
        track_behavior: String(formData.get("track_behavior") ?? "continue"),
        stream_url: streamUrl || null,
      });
      await refreshDetail(detail.item.id);
      setLinkMessage("Track saved.");
    } catch (trackError) {
      setError(trackError instanceof Error ? trackError.message : "Failed to save track.");
    }
  }

  async function handleMoveTrack(trackId: number, direction: -1 | 1) {
    if (!detail) return;
    const sortedTracks = [...detail.tracks].sort((first, second) => first.track_number - second.track_number);
    const index = sortedTracks.findIndex((track) => track.id === trackId);
    const swapWith = index + direction;
    if (index < 0 || swapWith < 0 || swapWith >= sortedTracks.length) {
      return;
    }
    setError(null);
    try {
      await Promise.all([
        updatePlaylistTrack(detail.item.id, sortedTracks[index].id, {
          track_number: sortedTracks[swapWith].track_number,
        }),
        updatePlaylistTrack(detail.item.id, sortedTracks[swapWith].id, {
          track_number: sortedTracks[index].track_number,
        }),
      ]);
      await refreshDetail(detail.item.id);
      setLinkMessage("Track order updated.");
    } catch (moveError) {
      setError(moveError instanceof Error ? moveError.message : "Failed to move track.");
    }
  }

  async function handleRenumberTracks() {
    if (!detail) return;
    const sortedTracks = [...detail.tracks].sort((first, second) => first.track_number - second.track_number);
    setError(null);
    try {
      await Promise.all(
        sortedTracks.map((track, index) =>
          updatePlaylistTrack(detail.item.id, track.id, { track_number: index + 1 }),
        ),
      );
      await refreshDetail(detail.item.id);
      setLinkMessage("Tracks renumbered.");
    } catch (renumberError) {
      setError(renumberError instanceof Error ? renumberError.message : "Failed to renumber tracks.");
    }
  }

  async function handleApplyTrackBehavior() {
    if (!detail) return;
    setError(null);
    try {
      await Promise.all(
        detail.tracks.map((track) =>
          updatePlaylistTrack(detail.item.id, track.id, { track_behavior: bulkTrackBehavior }),
        ),
      );
      await refreshDetail(detail.item.id);
      setLinkMessage("Track behavior applied.");
    } catch (behaviorError) {
      setError(behaviorError instanceof Error ? behaviorError.message : "Failed to apply behavior.");
    }
  }

  async function handleAddRadioStream(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail) return;
    setError(null);
    try {
      await createRadioStreamTrack(detail.item.id, {
        title: radioForm.title,
        stream_url: radioForm.stream_url,
        icon_path: radioForm.icon_path || null,
      });
      await refreshDetail(detail.item.id);
      setRadioForm({ title: "", stream_url: "", icon_path: "" });
      setLinkMessage("Radio stream saved and validation queued.");
    } catch (radioError) {
      setError(radioError instanceof Error ? radioError.message : "Failed to add radio stream.");
    }
  }

  async function handleAddPodcast(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail) return;
    setError(null);
    try {
      await createPodcastFeed(detail.item.id, {
        title: podcastForm.title || null,
        rss_url: podcastForm.rss_url,
      });
      await refreshDetail(detail.item.id);
      setPodcastForm({ title: "", rss_url: "" });
      setLinkMessage("Podcast feed saved and inspection queued.");
    } catch (podcastError) {
      setError(podcastError instanceof Error ? podcastError.message : "Failed to add podcast.");
    }
  }

  async function handleAddSplitPoint(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail) return;
    setError(null);
    try {
      await createSplitPoint(detail.item.id, {
        timestamp_seconds: Number(splitForm.timestamp_seconds),
        title: splitForm.title,
        part_number: splitForm.part_number ? Number(splitForm.part_number) : null,
      });
      await refreshDetail(detail.item.id);
      setSplitForm({ timestamp_seconds: "", title: "", part_number: "" });
      setLinkMessage("Split point saved.");
    } catch (splitError) {
      setError(splitError instanceof Error ? splitError.message : "Failed to save split point.");
    }
  }

  async function handleLinkToCard(itemId: number) {
    if (!selectedCardId) {
      setError("Choose a card first.");
      return;
    }

    setLinking(true);
    setError(null);
    setLinkMessage(null);
    try {
      const result = await linkLibraryItemToCard(itemId, Number(selectedCardId));
      setItems((current) =>
        current.map((item) => (item.id === result.library_item.id ? result.library_item : item)),
      );
      setCards((current) =>
        current.map((card) => (card.id === result.card.id ? result.card : card)),
      );
      setLinkMessage(
        result.requires_split_plan
          ? `Queued card planning for ${result.card.display_name}.`
          : `Queued Yoto upload for ${result.card.display_name}.`,
      );
      setActiveLinkItemId(null);
    } catch (linkError) {
      setError(linkError instanceof Error ? linkError.message : "Failed to link card.");
    } finally {
      setLinking(false);
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Library</p>
          <h2>Media library</h2>
        </div>
        <span className="status-pill">{items.length} items</span>
      </div>
      {error ? <p className="auth-error">{error}</p> : null}
      <div className="filter-bar">
        <input
          onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
          placeholder="Search library"
          value={filters.search}
        />
        <select
          onChange={(event) => setFilters((current) => ({ ...current, content_type: event.target.value }))}
          value={filters.content_type}
        >
          <option value="">All types</option>
          {contentTypes.map((contentType) => (
            <option key={contentType} value={contentType}>
              {contentType}
            </option>
          ))}
        </select>
        <select
          onChange={(event) => setFilters((current) => ({ ...current, tag_id: event.target.value }))}
          value={filters.tag_id}
        >
          <option value="">All tags</option>
          {tags.map((tag) => (
            <option key={tag.id} value={tag.id}>
              {tag.name}
            </option>
          ))}
        </select>
      </div>
      {items.length === 0 ? (
        <EmptyState message="No library items yet. Create an import to seed the library." />
      ) : (
        <div className="item-list">
          {items.map((item) => (
            <article className="list-row" key={item.id}>
              <div>
                <h3>{item.title}</h3>
                <p className="muted">
                  {item.content_type} · {item.status}
                  {item.stream_url ? " · Live stream" : ""}
                </p>
                {item.tags.length > 0 ? (
                  <div className="tag-chip-row">
                    {item.tags.map((tag) => (
                      <span className="tag-chip" key={tag.id} style={{ borderColor: tag.color ?? undefined }}>
                        {tag.name}
                      </span>
                    ))}
                  </div>
                ) : null}
                {item.media_url || item.stream_url ? (
                  <div className="library-player">
                    <AudioPlayer
                      customAdditionalControls={[]}
                      customVolumeControls={[]}
                      layout="horizontal-reverse"
                      preload={item.stream_url ? "none" : "metadata"}
                      showJumpControls={false}
                      src={item.media_url ?? item.stream_url ?? undefined}
                    />
                  </div>
                ) : null}
                {activeLinkItemId === item.id ? (
                  <div className="inline-link-panel">
                    {cards.length === 0 ? (
                      <p className="muted">No cards available yet.</p>
                    ) : (
                      <label>
                        Card
                        <select
                          onChange={(event) => setSelectedCardId(event.target.value)}
                          value={selectedCardId}
                        >
                          {cards.map((card) => (
                            <option key={card.id} value={card.id}>
                              {card.display_name} ({card.card_code})
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                    <div className="row-actions">
                      <button
                        className="primary-button"
                        disabled={linking || cards.length === 0}
                        onClick={() => void handleLinkToCard(item.id)}
                        type="button"
                      >
                        {linking ? "Queueing" : "Queue link"}
                      </button>
                      <button
                        className="ghost-button"
                        onClick={() => setActiveLinkItemId(null)}
                        type="button"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
              <div className="row-actions">
                <Link className="ghost-button" to={`/library/${item.id}`}>
                  Details
                </Link>
                <button
                  className="ghost-button"
                  onClick={() => void openDetailPanel(item.id)}
                  type="button"
                >
                  Options
                </button>
                <button
                  className="ghost-button"
                  onClick={() => void openLinkPanel(item.id)}
                  type="button"
                >
                  Link to card
                </button>
                <span className="status-pill status-pill-muted">#{item.id}</span>
              </div>
            </article>
          ))}
        </div>
      )}
      {detail ? (
        <div className="detail-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Card prep</p>
              <h2>{detail.item.title}</h2>
            </div>
            <button className="ghost-button" onClick={() => setDetail(null)} type="button">
              Close
            </button>
          </div>

          <div className="prep-grid">
            <div className="prep-block">
              <h3>Playlist options</h3>
              <label>
                Cover path
                <input
                  onChange={(event) => setCoverArtPath(event.target.value)}
                  placeholder="/artwork/moon.png"
                  value={coverArtPath}
                />
              </label>
              <label className="file-picker compact-file-picker">
                <span>{coverArtFile ? coverArtFile.name : "Choose cover image"}</span>
                <input
                  accept=".jpg,.jpeg,.png,.webp"
                  onChange={(event) => setCoverArtFile(event.target.files?.[0] ?? null)}
                  type="file"
                />
              </label>
              <button
                className="ghost-button"
                disabled={!coverArtFile}
                onClick={() => void handleUploadCoverArt()}
                type="button"
              >
                Upload cover
              </button>
              <label className="checkbox-row">
                <input
                  checked={detail.item.playlist_always_play_from_start}
                  onChange={(event) =>
                    setDetailOption("playlist_always_play_from_start", event.target.checked)
                  }
                  type="checkbox"
                />
                Always play from start
              </label>
              <label className="checkbox-row">
                <input
                  checked={detail.item.playlist_shuffle_tracks}
                  onChange={(event) =>
                    setDetailOption("playlist_shuffle_tracks", event.target.checked)
                  }
                  type="checkbox"
                />
                Shuffle tracks
              </label>
              <label className="checkbox-row">
                <input
                  checked={detail.item.playlist_hide_track_numbers}
                  onChange={(event) =>
                    setDetailOption("playlist_hide_track_numbers", event.target.checked)
                  }
                  type="checkbox"
                />
                Hide track numbers
              </label>
              <button className="primary-button" onClick={() => void handleSavePlaylistSettings()} type="button">
                Save options
              </button>
            </div>

            <div className="prep-block">
              <h3>Tags</h3>
              {tags.length === 0 ? (
                <EmptyState message="No tags available yet." />
              ) : (
                <div className="tag-checkbox-list">
                  {tags.map((tag) => (
                    <label className="checkbox-row" key={tag.id}>
                      <input
                        checked={selectedTagIds.includes(tag.id)}
                        onChange={(event) =>
                          setSelectedTagIds((current) =>
                            event.target.checked
                              ? Array.from(new Set([...current, tag.id]))
                              : current.filter((tagId) => tagId !== tag.id),
                          )
                        }
                        type="checkbox"
                      />
                      {tag.name}
                    </label>
                  ))}
                </div>
              )}
              <button className="primary-button" onClick={() => void handleSaveTags()} type="button">
                Save tags
              </button>
            </div>

            <div className="prep-block">
              <h3>Track icons</h3>
              <label>
                Icon path
                <input
                  onChange={(event) => setTrackIconPath(event.target.value)}
                  placeholder="/icons/book.png"
                  value={trackIconPath}
                />
              </label>
              <button
                className="ghost-button"
                disabled={!trackIconPath || detail.tracks.length === 0}
                onClick={() => void handleApplyIcon()}
                type="button"
              >
                Apply to all tracks
              </button>
              <p className="muted">
                {detail.tracks.length} tracks ·{" "}
                {detail.tracks.filter((track) => !track.icon_path).length} missing icons
              </p>
            </div>

            <form className="prep-block" onSubmit={(event) => void handleAddRadioStream(event)}>
              <h3>Radio stream</h3>
              <input
                onChange={(event) =>
                  setRadioForm((current) => ({ ...current, title: event.target.value }))
                }
                placeholder="Stream title"
                required
                value={radioForm.title}
              />
              <input
                onChange={(event) =>
                  setRadioForm((current) => ({ ...current, stream_url: event.target.value }))
                }
                placeholder="https://example.test/stream.mp3"
                required
                value={radioForm.stream_url}
              />
              <input
                onChange={(event) =>
                  setRadioForm((current) => ({ ...current, icon_path: event.target.value }))
                }
                placeholder="/icons/radio.png"
                value={radioForm.icon_path}
              />
              <button className="primary-button" type="submit">
                Add stream
              </button>
            </form>

            <form className="prep-block" onSubmit={(event) => void handleAddPodcast(event)}>
              <h3>Podcast feed</h3>
              <input
                onChange={(event) =>
                  setPodcastForm((current) => ({ ...current, title: event.target.value }))
                }
                placeholder="Optional title"
                value={podcastForm.title}
              />
              <input
                onChange={(event) =>
                  setPodcastForm((current) => ({ ...current, rss_url: event.target.value }))
                }
                placeholder="https://example.test/feed.xml"
                required
                value={podcastForm.rss_url}
              />
              <button className="primary-button" type="submit">
                Add feed
              </button>
            </form>

            <form className="prep-block" onSubmit={(event) => void handleAddSplitPoint(event)}>
              <h3>Manual split point</h3>
              <input
                min="0"
                onChange={(event) =>
                  setSplitForm((current) => ({ ...current, timestamp_seconds: event.target.value }))
                }
                placeholder="Timestamp seconds"
                required
                type="number"
                value={splitForm.timestamp_seconds}
              />
              <input
                onChange={(event) =>
                  setSplitForm((current) => ({ ...current, title: event.target.value }))
                }
                placeholder="Part title"
                required
                value={splitForm.title}
              />
              <input
                min="1"
                onChange={(event) =>
                  setSplitForm((current) => ({ ...current, part_number: event.target.value }))
                }
                placeholder="Part number"
                type="number"
                value={splitForm.part_number}
              />
              <button className="primary-button" type="submit">
                Save split
              </button>
            </form>

            <div className="prep-block">
              <h3>Readiness</h3>
              {detailLoading ? <p className="muted">Loading checks...</p> : null}
              {readiness ? (
                <div className="check-list">
                  {readiness.checks.map((check) => (
                    <div className="check-row" key={check.key}>
                      <span className={check.ok ? "check-ok" : "check-warn"}>
                        {check.ok ? "OK" : "Needs review"}
                      </span>
                      <div>
                        <strong>{check.label}</strong>
                        <p className="muted">{check.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <div className="track-editor-panel">
            <div className="section-header">
              <div>
                <p className="eyebrow">Tracks</p>
                <h2>Track editor</h2>
              </div>
              <span className="status-pill">{detail.tracks.length} tracks</span>
            </div>
            {detail.tracks.length > 0 ? (
              <div className="track-editor-toolbar">
                <label>
                  Bulk behavior
                  <select
                    onChange={(event) => setBulkTrackBehavior(event.target.value)}
                    value={bulkTrackBehavior}
                  >
                    <option value="continue">Continue</option>
                    <option value="pause_for_button">Pause for button</option>
                    <option value="repeat_track">Repeat track</option>
                  </select>
                </label>
                <button className="secondary-button" onClick={() => void handleApplyTrackBehavior()} type="button">
                  Apply behavior
                </button>
                <button className="secondary-button" onClick={() => void handleRenumberTracks()} type="button">
                  Renumber tracks
                </button>
              </div>
            ) : null}
            {detail.tracks.length === 0 ? (
              <EmptyState message="No tracks yet. Add a radio stream or import a ZIP album to create track rows." />
            ) : (
              <div className="track-editor-list">
                {detail.tracks.map((track, trackIndex) => (
                  <form
                    className="track-editor-row"
                    key={track.id}
                    onSubmit={(event) => void handleUpdateTrack(event, track.id)}
                  >
                    <label>
                      Title
                      <input defaultValue={track.title} name="title" required />
                    </label>
                    <label>
                      Order
                      <input
                        defaultValue={track.track_number}
                        min="1"
                        name="track_number"
                        required
                        type="number"
                      />
                    </label>
                    <label>
                      Behavior
                      <select defaultValue={track.track_behavior} name="track_behavior">
                        <option value="continue">Continue</option>
                        <option value="pause_for_button">Pause for button</option>
                        <option value="repeat_track">Repeat track</option>
                      </select>
                    </label>
                    <label>
                      Duration seconds
                      <input
                        defaultValue={track.duration_seconds ?? ""}
                        min="0"
                        name="duration_seconds"
                        type="number"
                      />
                    </label>
                    <label>
                      Icon path
                      <input defaultValue={track.icon_path ?? ""} name="icon_path" />
                    </label>
                    <label>
                      Source URL
                      <input defaultValue={track.source_url ?? ""} name="source_url" />
                    </label>
                    <label>
                      Start seconds
                      <input
                        defaultValue={track.source_start_seconds ?? ""}
                        min="0"
                        name="source_start_seconds"
                        type="number"
                      />
                    </label>
                    <label>
                      End seconds
                      <input
                        defaultValue={track.source_end_seconds ?? ""}
                        min="0"
                        name="source_end_seconds"
                        type="number"
                      />
                    </label>
                    <label>
                      Stream URL
                      <input defaultValue={track.stream_url ?? ""} name="stream_url" />
                    </label>
                    <div className="track-editor-actions">
                      <span className="status-pill status-pill-muted">
                        {track.is_stream ? "Stream" : `Track ${track.track_number}`}
                      </span>
                      <button
                        className="secondary-button"
                        disabled={trackIndex === 0}
                        onClick={() => void handleMoveTrack(track.id, -1)}
                        type="button"
                      >
                        Up
                      </button>
                      <button
                        className="secondary-button"
                        disabled={trackIndex === detail.tracks.length - 1}
                        onClick={() => void handleMoveTrack(track.id, 1)}
                        type="button"
                      >
                        Down
                      </button>
                      <button className="primary-button" type="submit">
                        Save track
                      </button>
                    </div>
                  </form>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}
      {linkMessage ? <p className="muted">{linkMessage}</p> : null}
    </section>
  );
}

function LibraryDetailPage() {
  const { itemId } = useParams();
  const numericItemId = Number(itemId);
  const [detail, setDetail] = useState<LibraryItemDetail | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [cardPlan, setCardPlan] = useState<CardPlan | null>(null);
  const [savedCardPlan, setSavedCardPlan] = useState<CardPlan | null>(null);
  const [cardPlanDraft, setCardPlanDraft] = useState<Record<number, number>>({});
  const [versions, setVersions] = useState<VersionEvent[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [yotoPlaylists, setYotoPlaylists] = useState<YotoPlaylistDraft[]>([]);
  const [yotoPlaylistVersions, setYotoPlaylistVersions] = useState<Record<number, YotoPlaylistVersion[]>>({});
  const [yotoRemotePayloads, setYotoRemotePayloads] = useState<Record<number, YotoPlaylistRemotePayload>>({});
  const [yotoRemotePayloadEditors, setYotoRemotePayloadEditors] = useState<Record<number, string>>({});
  const [yotoRemoteLinks, setYotoRemoteLinks] = useState<
    Record<number, { remotePlaylistId: string; remotePlaylistUri: string; markLinkedManually: boolean }>
  >({});
  const [yotoLiveCreateResults, setYotoLiveCreateResults] = useState<Record<number, CreateLiveYotoPlaylistResponse>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshPage() {
    if (!Number.isFinite(numericItemId)) {
      throw new Error("Invalid library item.");
    }
    const [
      nextDetail,
      nextReadiness,
      nextCardPlan,
      nextSavedCardPlan,
      nextVersions,
      nextJobs,
      nextYotoPlaylists,
    ] = await Promise.all([
      fetchLibraryItemDetail(numericItemId),
      fetchReadiness(numericItemId),
      fetchCardPlan(numericItemId),
      fetchSavedCardPlan(numericItemId),
      fetchLibraryItemVersions(numericItemId),
      fetchJobs(),
      fetchYotoPlaylists(numericItemId),
    ]);
    setDetail(nextDetail);
    setReadiness(nextReadiness);
    setCardPlan(nextCardPlan);
    setSavedCardPlan(nextSavedCardPlan);
    setCardPlanDraft(cardPlanAssignments(nextSavedCardPlan.parts.length > 0 ? nextSavedCardPlan : nextCardPlan));
    setVersions(nextVersions);
    setJobs(nextJobs.filter((job) => job.related_library_item_id === numericItemId));
    setYotoPlaylists(nextYotoPlaylists);
    const versionEntries = await Promise.all(
      nextYotoPlaylists.map(async (playlist) => [playlist.id, await fetchYotoPlaylistVersions(playlist.id)] as const),
    );
    const remotePayloadEntries = await Promise.all(
      nextYotoPlaylists.map(async (playlist) => [playlist.id, await fetchYotoPlaylistRemotePayload(playlist.id)] as const),
    );
    setYotoPlaylistVersions(Object.fromEntries(versionEntries));
    const remotePayloadMap = Object.fromEntries(remotePayloadEntries);
    setYotoRemotePayloads(remotePayloadMap);
    setYotoRemotePayloadEditors((current) =>
      Object.fromEntries(
        nextYotoPlaylists.map((playlist) => [
          playlist.id,
          current[playlist.id] ??
            JSON.stringify(remotePayloadMap[playlist.id]?.payload ?? playlist.payload, null, 2),
        ]),
      ),
    );
    setYotoRemoteLinks((current) =>
      Object.fromEntries(
        nextYotoPlaylists.map((playlist) => [
          playlist.id,
          current[playlist.id] ?? {
            remotePlaylistId: playlist.remote_playlist_id ?? "",
            remotePlaylistUri: playlist.remote_playlist_uri ?? "",
            markLinkedManually: false,
          },
        ]),
      ),
    );
  }

  useEffect(() => {
    setLoading(true);
    void refreshPage()
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "Failed to load item detail."),
      )
      .finally(() => setLoading(false));
  }, [numericItemId]);

  async function handleRetry(jobId: number) {
    setError(null);
    try {
      await retryJob(jobId);
      await refreshPage();
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "Retry failed.");
    }
  }

  async function handleQueueProcessing() {
    setError(null);
    try {
      await queueLibraryItemProcessing(numericItemId);
      await refreshPage();
    } catch (processError) {
      setError(processError instanceof Error ? processError.message : "Processing queue failed.");
    }
  }

  async function handleQueueYotoPlaylist() {
    setError(null);
    try {
      await queueYotoPlaylist(numericItemId);
      await refreshPage();
    } catch (queueError) {
      setError(queueError instanceof Error ? queueError.message : "Yoto playlist queue failed.");
    }
  }

  async function handleRestoreYotoPlaylistVersion(playlistId: number, versionId: number) {
    setError(null);
    try {
      await restoreYotoPlaylistVersion(playlistId, versionId);
      await refreshPage();
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Yoto playlist restore failed.");
    }
  }

  async function handleSaveYotoRemoteLink(playlistId: number) {
    const mapping = yotoRemoteLinks[playlistId];
    if (!mapping) {
      return;
    }
    setError(null);
    try {
      await updateYotoPlaylistRemoteLink(playlistId, {
        remote_playlist_id: mapping.remotePlaylistId.trim() || null,
        remote_playlist_uri: mapping.remotePlaylistUri.trim() || null,
        mark_linked_manually: mapping.markLinkedManually,
      });
      await refreshPage();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Yoto remote playlist mapping failed.");
    }
  }

  async function handleCreateLiveYotoPlaylist(playlistId: number) {
    const rawEditorValue = yotoRemotePayloadEditors[playlistId]?.trim();
    let requestPayload: Record<string, unknown> | null | undefined;
    if (rawEditorValue) {
      try {
        requestPayload = JSON.parse(rawEditorValue) as Record<string, unknown>;
      } catch {
        setError("The generated Yoto payload editor contains invalid JSON.");
        return;
      }
    }

    setError(null);
    try {
      const result = await createLiveYotoPlaylist(playlistId, {
        request_payload: requestPayload,
        mark_linked_cards_ready: true,
      });
      setYotoLiveCreateResults((current) => ({ ...current, [playlistId]: result }));
      await refreshPage();
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Live Yoto playlist creation failed.");
    }
  }

  async function handleQueueArtworkPixelise() {
    setError(null);
    try {
      await queueArtworkPixelise(numericItemId);
      await refreshPage();
    } catch (artworkError) {
      setError(artworkError instanceof Error ? artworkError.message : "Artwork pixelisation queue failed.");
    }
  }

  async function handleSaveCardPlan() {
    if (!cardPlan) return;
    setError(null);
    try {
      const maxPart = Math.max(1, ...Object.values(cardPlanDraft));
      const parts = Array.from({ length: maxPart }, (_, index) => {
        const partNumber = index + 1;
        return {
          part_number: partNumber,
          title: `${detail?.item.title ?? "Card"} - Part ${partNumber}`,
          track_ids: cardPlan.parts
            .flatMap((part) => part.tracks)
            .filter((track) => (cardPlanDraft[track.track_id] || 1) === partNumber)
            .map((track) => track.track_id),
        };
      }).filter((part) => part.track_ids.length > 0);
      const saved = await saveCardPlan(numericItemId, { parts });
      setSavedCardPlan(saved);
      setCardPlanDraft(cardPlanAssignments(saved));
      await refreshPage();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Card plan save failed.");
    }
  }

  async function handleRestoreVersion(version: VersionEvent) {
    const confirmed = window.confirm(
      `Restore ${detail?.item.title ?? "this item"} to version ${version.version_number}? This will create a new version event.`,
    );
    if (!confirmed) return;

    setError(null);
    try {
      await restoreLibraryItemVersion(numericItemId, version.id);
      await refreshPage();
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Restore failed.");
    }
  }

  if (loading) {
    return (
      <section className="panel">
        <p className="eyebrow">Library</p>
        <h2>Loading item</h2>
      </section>
    );
  }

  if (!detail) {
    return (
      <section className="panel">
        <p className="eyebrow">Library</p>
        <h2>Item unavailable</h2>
        {error ? <p className="auth-error">{error}</p> : null}
        <Link className="ghost-button" to="/">
          Back to library
        </Link>
      </section>
    );
  }

  const totalDuration = detail.tracks.reduce(
    (total, track) => total + (track.duration_seconds ?? 0),
    0,
  );
  const yotoSteps = yotoPlaylistWorkflowSteps(detail, jobs, yotoPlaylists);
  const yotoSummary = workflowStatusSummary(yotoSteps);
  const currentYotoPlaylist = latestYotoPlaylist(yotoPlaylists);

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Library detail</p>
          <h2>{detail.item.title}</h2>
          <p className="muted">
            {detail.item.content_type} · {detail.item.status} · {detail.item.readiness_status}
          </p>
        </div>
        <div className="row-actions">
          <button className="ghost-button" onClick={() => void refreshPage()} type="button">
            Refresh
          </button>
          <button className="primary-button" onClick={() => void handleQueueProcessing()} type="button">
            Process audio
          </button>
          <Link className="ghost-button" to="/">
            Back
          </Link>
        </div>
      </div>

      {error ? <p className="auth-error">{error}</p> : null}

      {detail.item.media_url || detail.item.stream_url ? (
        <div className="library-player detail-player">
          <AudioPlayer
            customAdditionalControls={[]}
            customVolumeControls={[]}
            layout="horizontal-reverse"
            preload={detail.item.stream_url ? "none" : "metadata"}
            showJumpControls={false}
            src={detail.item.media_url ?? detail.item.stream_url ?? undefined}
          />
        </div>
      ) : null}

      <div className="detail-summary-grid">
        <div className="summary-tile">
          <span className="summary-label">Tracks</span>
          <strong>{detail.tracks.length}</strong>
        </div>
        <div className="summary-tile">
          <span className="summary-label">Duration</span>
          <strong>{totalDuration ? formatDuration(totalDuration) : "Unknown"}</strong>
        </div>
        <div className="summary-tile">
          <span className="summary-label">Split points</span>
          <strong>{detail.split_points.length}</strong>
        </div>
        <div className="summary-tile">
          <span className="summary-label">Jobs</span>
          <strong>{jobs.length}</strong>
        </div>
        <div className="summary-tile">
          <span className="summary-label">Versions</span>
          <strong>{versions.length}</strong>
        </div>
        <div className="summary-tile">
          <span className="summary-label">Assets</span>
          <strong>{detail.processed_assets.length}</strong>
        </div>
      </div>

      <div className="detail-note workflow-overview-panel">
        <p className="eyebrow">Yoto workflow</p>
        <h3>{yotoSummary.title}</h3>
        <p>{yotoSummary.detail}</p>
        <div className="workflow-fact-row">
          <span className={`status-pill${currentYotoPlaylist?.remote_playlist_uri || currentYotoPlaylist?.remote_playlist_id ? "" : " status-pill-muted"}`}>
            Cloud {currentYotoPlaylist?.remote_playlist_uri || currentYotoPlaylist?.remote_playlist_id ? "created" : "pending"}
          </span>
          <span className="status-pill status-pill-muted">
            Draft {currentYotoPlaylist?.status ?? "not queued"}
          </span>
          <span className="status-pill status-pill-muted">
            Next {yotoSteps.find((step) => !step.done)?.label ?? "Verify physical card"}
          </span>
        </div>
      </div>

      {detail.item.readiness_detail ? (
        <div className="detail-note">
          <p className="eyebrow">Inspection</p>
          <p>{detail.item.readiness_detail}</p>
        </div>
      ) : null}

      <div className="detail-two-column">
        <div className="prep-block">
          <h3>Readiness</h3>
          {readiness ? (
            <div className="check-list">
              {readiness.checks.map((check) => (
                <div className="check-row" key={check.key}>
                  <span className={check.ok ? "check-ok" : "check-warn"}>
                    {check.ok ? "OK" : "Review"}
                  </span>
                  <div>
                    <strong>{check.label}</strong>
                    <p className="muted">{check.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No readiness checks available." />
          )}
        </div>

        <div className="prep-block">
          <h3>Playlist settings</h3>
          <p className="muted">Cover: {detail.item.cover_art_path ?? "Not set"}</p>
          <p className="muted">
            {detail.item.playlist_always_play_from_start ? "Play from start" : "Resume allowed"} ·{" "}
            {detail.item.playlist_shuffle_tracks ? "Shuffle" : "Ordered"} ·{" "}
            {detail.item.playlist_hide_track_numbers ? "Track numbers hidden" : "Track numbers shown"}
          </p>
        </div>
      </div>

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Artwork</p>
            <h2>Cover assets</h2>
          </div>
          <button className="primary-button" onClick={() => void handleQueueArtworkPixelise()} type="button">
            Pixelise cover
          </button>
        </div>
        {detail.artwork_assets.length === 0 ? (
          <EmptyState message="No artwork assets recorded yet." />
        ) : (
          <div className="compact-table">
            {detail.artwork_assets.map((asset) => (
              <div className="compact-table-row" key={asset.id}>
                <span className="status-pill status-pill-muted">{asset.kind}</span>
                <div>
                  <strong>{asset.output_path ?? asset.source_path}</strong>
                  <p className="muted">
                    {asset.status} · {asset.width && asset.height ? `${asset.width}x${asset.height}` : "source"} ·{" "}
                    {asset.palette ?? "original"}
                  </p>
                </div>
                <span className="muted">{asset.checksum_sha256?.slice(0, 8) ?? "pending"}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Tracks</p>
            <h2>Playlist tracks</h2>
          </div>
          <span className="status-pill">{detail.tracks.length} tracks</span>
        </div>
        {detail.tracks.length === 0 ? (
          <EmptyState message="No tracks discovered yet." />
        ) : (
          <div className="compact-table">
            {detail.tracks.map((track) => (
              <div className="compact-table-row" key={track.id}>
                <span className="status-pill status-pill-muted">#{track.track_number}</span>
                <div>
                  <strong>{track.title}</strong>
                  <p className="muted">
                    {formatDuration(track.duration_seconds)} ·{" "}
                    {track.is_stream ? "Stream" : track.track_behavior}
                    {track.source_start_seconds !== null ? ` · starts ${formatDuration(track.source_start_seconds)}` : ""}
                    {track.source_end_seconds !== null ? ` · ends ${formatDuration(track.source_end_seconds)}` : ""}
                  </p>
                </div>
                <span className="muted">{track.icon_path ?? "No icon"}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Card plan</p>
            <h2>Proposed parts</h2>
          </div>
          <span className="status-pill">
            {cardPlan ? `${cardPlan.parts.length} parts` : "No plan"}
          </span>
        </div>
        {cardPlan && cardPlan.parts.length > 0 ? (
          <div className="card-plan-list">
            <div className="row-actions">
              <button className="primary-button" onClick={() => void handleSaveCardPlan()} type="button">
                Save card plan
              </button>
              <span className="status-pill status-pill-muted">
                {savedCardPlan && savedCardPlan.parts.length > 0 ? "Saved plan available" : "Preview draft"}
              </span>
            </div>
            {cardPlan.parts.map((part) => (
              <article className="card-plan-part" key={part.part_number}>
                <div className="section-header">
                  <div>
                    <h3>{part.title}</h3>
                    <p className="muted">
                      {formatDuration(part.duration_seconds)} · {part.estimated_size_mb} MB ·{" "}
                      {part.track_count} tracks
                    </p>
                  </div>
                  <span className="status-pill status-pill-muted">Part {part.part_number}</span>
                </div>
                {part.warnings.length > 0 ? (
                  <p className="auth-error">{part.warnings.join(" ")}</p>
                ) : null}
                <div className="compact-list">
                  {part.tracks.map((track) => (
                    <label className="plan-track-row" key={track.track_id}>
                      <span>
                        #{track.track_number} {track.title} · {formatDuration(track.duration_seconds)}
                        {track.estimated_size_mb !== null ? ` · ${track.estimated_size_mb} MB` : ""}
                      </span>
                      <select
                        onChange={(event) =>
                          setCardPlanDraft((current) => ({
                            ...current,
                            [track.track_id]: Number(event.target.value),
                          }))
                        }
                        value={cardPlanDraft[track.track_id] || part.part_number}
                      >
                        {Array.from({ length: Math.max(cardPlan.parts.length + 1, 2) }, (_, index) => index + 1).map(
                          (partNumber) => (
                            <option key={partNumber} value={partNumber}>
                              Part {partNumber}
                            </option>
                          ),
                        )}
                      </select>
                    </label>
                  ))}
                </div>
              </article>
            ))}
            {cardPlan.warnings.length > 0 ? (
              <p className="auth-error">{cardPlan.warnings.join(" ")}</p>
            ) : null}
          </div>
        ) : (
          <EmptyState message="No plan yet. Inspect media or add tracks first." />
        )}
        {savedCardPlan && savedCardPlan.parts.length > 0 ? (
          <div className="saved-plan-summary">
            <h3>Saved plan</h3>
            {savedCardPlan.parts.map((part) => (
              <p className="muted" key={part.part_number}>
                Part {part.part_number}: {part.track_count} tracks · {formatDuration(part.duration_seconds)}
              </p>
            ))}
          </div>
        ) : null}
      </div>

      <div className="detail-two-column">
        <div className="prep-block">
          <h3>Split points</h3>
          {detail.split_points.length === 0 ? (
            <EmptyState message="No manual split points." />
          ) : (
            <div className="compact-list">
              {detail.split_points.map((splitPoint) => (
                <p className="muted" key={splitPoint.id}>
                  {formatDuration(splitPoint.timestamp_seconds)} · {splitPoint.title}
                  {splitPoint.part_number ? ` · Part ${splitPoint.part_number}` : ""}
                </p>
              ))}
            </div>
          )}
        </div>

        <div className="prep-block">
          <h3>Related jobs</h3>
          {jobs.length === 0 ? (
            <EmptyState message="No jobs linked to this item." />
          ) : (
            <div className="compact-list">
              {jobs.map((job) => (
                <div className="job-detail-row" key={job.id}>
                  <div>
                    <strong>{job.type}</strong>
                    <p className="muted">
                      {job.status} · {job.progress_percent}% · {job.progress_message}
                    </p>
                  </div>
                  {job.status === "failed" ? (
                    <button className="ghost-button" onClick={() => void handleRetry(job.id)} type="button">
                      Retry
                    </button>
                  ) : (
                    <span className="status-pill status-pill-muted">#{job.id}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Processed</p>
            <h2>Yoto-ready assets</h2>
          </div>
          <span className="status-pill">{detail.processed_assets.length} assets</span>
        </div>
        {detail.processed_assets.length === 0 ? (
          <EmptyState message="No processed audio assets yet." />
        ) : (
          <div className="compact-table">
            {detail.processed_assets.map((asset) => (
              <div className="compact-table-row" key={asset.id}>
                <span className="status-pill status-pill-muted">{asset.profile}</span>
                <div>
                  <strong>{asset.output_path}</strong>
                  <p className="muted">
                    {asset.codec} · {asset.bitrate_kbps} kbps · {asset.channels}ch ·{" "}
                    {formatDuration(asset.duration_seconds)}
                  </p>
                </div>
                <span className="muted">{Math.round(asset.size_bytes / 1024)} KB</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">Yoto</p>
            <h2>Playlist upload</h2>
          </div>
          <button className="primary-button" onClick={() => void handleQueueYotoPlaylist()} type="button">
            Queue Yoto playlist
          </button>
        </div>
        <p className="muted">
          Required for Yoto cloud create: a title, playlist draft, and playable uploaded tracks. Cover artwork is optional.
          If you do set cover art, Yoto only receives it when it is already a public <code>http(s)</code> image URL.
        </p>
        <WorkflowChecklist steps={yotoSteps} />
        {yotoPlaylists.length === 0 ? (
          <EmptyState message="No Yoto playlist drafts queued yet." />
        ) : (
          <div className="compact-table">
            {yotoPlaylists.map((playlist) => (
              <div className="compact-table-row" key={playlist.id}>
                <span className="status-pill status-pill-muted">{playlist.status}</span>
                <div>
                  <strong>{playlist.title}</strong>
                  <p className="muted">
                    Job {playlist.related_job_id ?? "pending"} ·{" "}
                    {playlist.remote_playlist_uri ?? playlist.remote_playlist_id ?? "Live create pending"}
                  </p>
                  <div className="inline-link-panel yoto-remote-link-panel">
                    <p className="muted">
                      Generated live payload
                      {yotoRemotePayloads[playlist.id]?.can_create_live ? " Â· ready" : " Â· review needed"}
                    </p>
                    {yotoRemotePayloads[playlist.id]?.warnings?.length ? (
                      <p className="auth-error">{yotoRemotePayloads[playlist.id]?.warnings.join(" ")}</p>
                    ) : null}
                    <label className="yoto-debug-body">
                      `POST /content` JSON
                      <textarea
                        onChange={(event) =>
                          setYotoRemotePayloadEditors((current) => ({
                            ...current,
                            [playlist.id]: event.target.value,
                          }))
                        }
                        rows={10}
                        value={yotoRemotePayloadEditors[playlist.id] ?? ""}
                      />
                    </label>
                    <div className="button-row">
                      <button
                        className="primary-button"
                        onClick={() => void handleCreateLiveYotoPlaylist(playlist.id)}
                        type="button"
                      >
                        Create live playlist and link cards
                      </button>
                    </div>
                    {yotoLiveCreateResults[playlist.id] ? (
                      <div className="settings-note">
                        <p>
                          Live create
                          {yotoLiveCreateResults[playlist.id]?.http_status
                            ? ` (${yotoLiveCreateResults[playlist.id]?.http_status})`
                            : ""}
                          {yotoLiveCreateResults[playlist.id]?.remote_card_id
                            ? ` Â· card ID ${yotoLiveCreateResults[playlist.id]?.remote_card_id}`
                            : ""}
                          {yotoLiveCreateResults[playlist.id]?.token_refreshed ? " Â· token refreshed" : ""}
                        </p>
                        {yotoLiveCreateResults[playlist.id]?.response_excerpt ? (
                          <pre>{yotoLiveCreateResults[playlist.id]?.response_excerpt}</pre>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                  <div className="inline-link-panel yoto-remote-link-panel">
                    <label>
                      Remote playlist ID
                      <input
                        onChange={(event) =>
                          setYotoRemoteLinks((current) => ({
                            ...current,
                            [playlist.id]: {
                              ...(current[playlist.id] ?? {
                                remotePlaylistId: "",
                                remotePlaylistUri: "",
                                markLinkedManually: false,
                              }),
                              remotePlaylistId: event.target.value,
                            },
                          }))
                        }
                        placeholder="playlist-123"
                        value={yotoRemoteLinks[playlist.id]?.remotePlaylistId ?? ""}
                      />
                    </label>
                    <label>
                      Remote playlist URI
                      <input
                        onChange={(event) =>
                          setYotoRemoteLinks((current) => ({
                            ...current,
                            [playlist.id]: {
                              ...(current[playlist.id] ?? {
                                remotePlaylistId: "",
                                remotePlaylistUri: "",
                                markLinkedManually: false,
                              }),
                              remotePlaylistUri: event.target.value,
                            },
                          }))
                        }
                        placeholder="https://my.yotoplay.com/playlist/playlist-123"
                        value={yotoRemoteLinks[playlist.id]?.remotePlaylistUri ?? ""}
                      />
                    </label>
                    <label className="checkbox-field">
                      <input
                        checked={yotoRemoteLinks[playlist.id]?.markLinkedManually ?? false}
                        onChange={(event) =>
                          setYotoRemoteLinks((current) => ({
                            ...current,
                            [playlist.id]: {
                              ...(current[playlist.id] ?? {
                                remotePlaylistId: "",
                                remotePlaylistUri: "",
                                markLinkedManually: false,
                              }),
                              markLinkedManually: event.target.checked,
                            },
                          }))
                        }
                        type="checkbox"
                      />
                      Mark linked cards as manually linked
                    </label>
                    <div className="button-row">
                      <button
                        className="secondary-button"
                        onClick={() => void handleSaveYotoRemoteLink(playlist.id)}
                        type="button"
                      >
                        Save remote mapping
                      </button>
                    </div>
                  </div>
                  {(yotoPlaylistVersions[playlist.id] ?? []).slice(0, 3).map((version) => (
                    <p className="muted" key={version.id}>
                      Version {version.version_number}: {version.summary}
                      {version.status !== "restored" ? (
                        <button
                          className="inline-button"
                          onClick={() => void handleRestoreYotoPlaylistVersion(playlist.id, version.id)}
                          type="button"
                        >
                          Restore
                        </button>
                      ) : null}
                    </p>
                  ))}
                </div>
                <span className="muted">
                  {yotoDraftChapterCount(playlist.payload)} tracks
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">History</p>
            <h2>Version events</h2>
          </div>
          <span className="status-pill">{versions.length} events</span>
        </div>
        {versions.length === 0 ? (
          <EmptyState message="No version events recorded for this item yet." />
        ) : (
          <div className="version-list">
            {versions.map((version) => (
              <article className="version-row" key={version.id}>
                <div>
                  <h3>Version {version.version_number}</h3>
                  <p className="muted">{version.summary}</p>
                </div>
                <div className="version-actions">
                  <span className="status-pill status-pill-muted">{version.event_type}</span>
                  <button
                    className="ghost-button"
                    onClick={() => void handleRestoreVersion(version)}
                    type="button"
                  >
                    Restore
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function ImportPage({ session }: { session: SessionResponse }) {
  const [imports, setImports] = useState<ImportRequest[]>([]);
  const [sources, setSources] = useState<ImportSourceInfo | null>(null);
  const [mode, setMode] = useState<"upload" | "filesystem">("upload");
  const [form, setForm] = useState({
    title: "",
    source_path: "",
    content_type: "Audiobook",
  });
  const [reviewingImportId, setReviewingImportId] = useState<number | null>(null);
  const [reviewForm, setReviewForm] = useState({
    title: "",
    content_type: "Audiobook",
    review_notes: "",
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function refreshImports() {
    setImports(await fetchImports());
  }

  useEffect(() => {
    void Promise.all([refreshImports(), fetchImportSources().then(setSources)]).catch((loadError) =>
      setError(loadError instanceof Error ? loadError.message : "Failed to load imports."),
    );
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      if (mode === "upload") {
        if (!selectedFile) {
          throw new Error("Choose a media file to upload.");
        }
        await uploadImport({
          title: form.title,
          content_type: form.content_type,
          requested_by_user_slug: session.user.slug,
          media_file: selectedFile,
        });
      } else {
        await createImport({
          title: form.title,
          source_type: "filesystem",
          source_path: form.source_path || null,
          content_type: form.content_type,
          requested_by_user_slug: session.user.slug,
        });
      }
      setForm({ title: "", source_path: "", content_type: "Audiobook" });
      setSelectedFile(null);
      await refreshImports();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Import failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleHideImport(importId: number) {
    setError(null);
    try {
      await hideImport(importId);
      await refreshImports();
    } catch (hideError) {
      setError(hideError instanceof Error ? hideError.message : "Hide failed.");
    }
  }

  function handleSelectReview(importRequest: ImportRequest) {
    setReviewingImportId(importRequest.id);
    setReviewForm({
      title: importRequest.title,
      content_type: importRequest.content_type,
      review_notes: importRequest.review_notes ?? "",
    });
  }

  async function handleSaveReview() {
    if (reviewingImportId === null) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await updateImportReview(reviewingImportId, {
        title: reviewForm.title,
        content_type: reviewForm.content_type,
        review_notes: reviewForm.review_notes || null,
        reviewed_by_user_slug: session.user.slug,
      });
      await refreshImports();
    } catch (reviewError) {
      setError(reviewError instanceof Error ? reviewError.message : "Import review failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleApproveReview() {
    if (reviewingImportId === null) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await approveImportReview(reviewingImportId, session.user.slug);
      await refreshImports();
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : "Import approval failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Import</p>
          <h2>Add media</h2>
        </div>
        <span className="status-pill">{imports.length} imports</span>
      </div>

      <div className="segmented-control" aria-label="Import source">
        <button
          className={mode === "upload" ? "segment-active" : ""}
          onClick={() => setMode("upload")}
          type="button"
        >
          Upload
        </button>
        <button
          className={mode === "filesystem" ? "segment-active" : ""}
          onClick={() => setMode("filesystem")}
          type="button"
        >
          Filesystem
        </button>
      </div>

      <form className="import-form" onSubmit={(event) => void handleSubmit(event)}>
        <div className="import-grid">
          <label>
            Title
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, title: event.target.value }))
              }
              required
              value={form.title}
            />
          </label>
          <label>
            Content type
            <select
              onChange={(event) =>
                setForm((current) => ({ ...current, content_type: event.target.value }))
              }
              value={form.content_type}
            >
              {contentTypes.map((contentType) => (
                <option key={contentType}>{contentType}</option>
              ))}
            </select>
          </label>
        </div>

        {mode === "upload" ? (
          <div className="drop-panel">
            <label className="file-picker">
              <span>{selectedFile ? selectedFile.name : "Choose media file"}</span>
              <input
                accept={sources?.allowed_extensions.join(",")}
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                type="file"
              />
            </label>
            <p className="muted">
              Uploads are staged in{" "}
              {sources?.browser_upload_path ?? "/var/lib/yotowebmgr/media/imports/uploads"}.
            </p>
          </div>
        ) : (
          <div className="drop-panel">
            <label>
              Source path
              <input
                onChange={(event) =>
                  setForm((current) => ({ ...current, source_path: event.target.value }))
                }
                placeholder={`${
                  sources?.filesystem_drop_path ?? "/var/lib/yotowebmgr/media/imports/drop"
                }/example.m4b`}
                value={form.source_path}
              />
            </label>
            <p className="muted">
              Filesystem imports are limited to{" "}
              {sources?.filesystem_drop_path ?? "/var/lib/yotowebmgr/media/imports/drop"}.
            </p>
          </div>
        )}

        <div className="form-actions">
          <span className="muted">Queued as {session.user.display_name}</span>
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "Queueing" : "Queue import"}
          </button>
        </div>
      </form>
      {error ? <p className="auth-error">{error}</p> : null}

      {reviewingImportId !== null ? (
        <div className="review-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Review</p>
              <h3>Import metadata</h3>
            </div>
            <span className="status-pill">
              {imports.find((item) => item.id === reviewingImportId)?.review_status ?? "review"}
            </span>
          </div>
          <div className="import-grid">
            <label>
              Title
              <input
                onChange={(event) =>
                  setReviewForm((current) => ({ ...current, title: event.target.value }))
                }
                value={reviewForm.title}
              />
            </label>
            <label>
              Content type
              <select
                onChange={(event) =>
                  setReviewForm((current) => ({ ...current, content_type: event.target.value }))
                }
                value={reviewForm.content_type}
              >
                {contentTypes.map((contentType) => (
                  <option key={contentType}>{contentType}</option>
                ))}
              </select>
            </label>
            <label>
              Notes
              <input
                onChange={(event) =>
                  setReviewForm((current) => ({ ...current, review_notes: event.target.value }))
                }
                value={reviewForm.review_notes}
              />
            </label>
          </div>
          <div className="button-row">
            <button
              className="secondary-button"
              disabled={submitting}
              onClick={() => void handleSaveReview()}
              type="button"
            >
              Save review
            </button>
            <button
              className="primary-button"
              disabled={submitting}
              onClick={() => void handleApproveReview()}
              type="button"
            >
              Approve import
            </button>
          </div>
        </div>
      ) : null}

      <h3 className="subsection-title">Recent imports</h3>
      <div className="item-list">
        {imports.length === 0 ? (
          <EmptyState message="No imports queued yet." />
        ) : (
          imports.map((item) => (
            <article className="list-row" key={item.id}>
              <div>
                <h3>{item.title}</h3>
                <p className="muted">
                  {item.source_type} · {item.content_type} · {item.status}
                </p>
                <p className="muted">
                  Review: {item.review_status}
                  {item.review_notes ? ` · ${item.review_notes}` : ""}
                </p>
              </div>
              <div className="row-actions">
                <span className="status-pill status-pill-muted">
                  Job {item.related_job_id ?? "pending"}
                </span>
                <button
                  className="ghost-button"
                  onClick={() => handleSelectReview(item)}
                  type="button"
                >
                  Review
                </button>
                <button
                  aria-label={`Hide ${item.title}`}
                  className="danger-icon-button"
                  onClick={() => void handleHideImport(item.id)}
                  title="Hide and mark ready for deletion"
                  type="button"
                >
                  x
                </button>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refreshJobs() {
    setJobs(await fetchJobs());
  }

  useEffect(() => {
    void refreshJobs().catch((loadError) =>
      setError(loadError instanceof Error ? loadError.message : "Failed to load jobs."),
    );
  }, []);

  async function handleRetry(jobId: number) {
    setError(null);
    try {
      await retryJob(jobId);
      await refreshJobs();
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "Retry failed.");
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Jobs</p>
          <h2>Background work</h2>
        </div>
        <button className="ghost-button" onClick={() => void refreshJobs()} type="button">
          Refresh
        </button>
      </div>
      {error ? <p className="auth-error">{error}</p> : null}
      {jobs.length === 0 ? (
        <EmptyState message="No jobs yet." />
      ) : (
        <div className="item-list">
          {jobs.map((job) => (
            <article className="list-row" key={job.id}>
              <div>
                <h3>{job.type}</h3>
                <p className="muted">
                  {job.status} · {job.progress_percent}% · {job.progress_message}
                </p>
              </div>
              {job.status === "failed" ? (
                <button className="ghost-button" onClick={() => void handleRetry(job.id)} type="button">
                  Retry
                </button>
              ) : (
                <span className="status-pill status-pill-muted">#{job.id}</span>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function TagsPage() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [form, setForm] = useState({ name: "", color: "#90cdf4" });
  const [error, setError] = useState<string | null>(null);

  async function refreshTags() {
    setTags(await fetchTags());
  }

  useEffect(() => {
    void refreshTags().catch((loadError) =>
      setError(loadError instanceof Error ? loadError.message : "Failed to load tags."),
    );
  }, []);

  async function handleCreateTag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await createTag({ name: form.name, color: form.color || null });
      setForm({ name: "", color: "#90cdf4" });
      await refreshTags();
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create tag.");
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Tags</p>
          <h2>Reusable tags</h2>
        </div>
        <span className="status-pill">{tags.length} tags</span>
      </div>
      {error ? <p className="auth-error">{error}</p> : null}
      <form className="import-form" onSubmit={(event) => void handleCreateTag(event)}>
        <div className="import-grid">
          <label>
            Name
            <input
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              required
              value={form.name}
            />
          </label>
          <label>
            Color
            <input
              onChange={(event) => setForm((current) => ({ ...current, color: event.target.value }))}
              type="color"
              value={form.color}
            />
          </label>
          <button className="primary-button" type="submit">
            Create tag
          </button>
        </div>
      </form>
      {tags.length === 0 ? (
        <EmptyState message="No tags yet." />
      ) : (
        <div className="tag-grid">
          {tags.map((tag) => (
            <article className="tag-row" key={tag.id}>
              <span className="tag-chip" style={{ borderColor: tag.color ?? undefined }}>
                {tag.name}
              </span>
              <span className="muted">{tag.usage_count} uses</span>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function CardsPage() {
  const [cards, setCards] = useState<PhysicalCard[]>([]);
  const [scanDumps, setScanDumps] = useState<CardScanDumpEntry[]>([]);
  const [stagedDump, setStagedDump] = useState<CardScanDumpEntry | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }
    const stored = window.localStorage.getItem(stagedCardDumpStorageKey);
    if (!stored) {
      return null;
    }
    try {
      return JSON.parse(stored) as CardScanDumpEntry;
    } catch {
      return null;
    }
  });
  const [error, setError] = useState<string | null>(null);
  const [scanMessage, setScanMessage] = useState<string | null>(null);
  const [helperMessage, setHelperMessage] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [nativeNfcSupported, setNativeNfcSupported] = useState(false);
  const [nativeWritePending, setNativeWritePending] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    card_code: "",
    programmable_id: "",
    nfc_serial_number: "",
    ndef_payload_text: "",
    ndef_payload_hex: "",
    scan_source: "manual",
    display_name: "",
    card_kind: "generic_mifare_ultralight_ev1",
    nfc_technology: "NFC Type 2",
    chip_type: "MIFARE Ultralight EV1",
    memory_size_bytes: "48",
    ndef_prepared: true,
    ndef_format_command: defaultNdefFormatCommand,
    programming_app: "NFC Tools",
    source_card_code: "",
    is_reusable_transfer_card: false,
    ready_to_link_in_app: false,
    linked_manually: false,
    overwrite_ok: false,
    downloaded_to_player_confirmed: false,
    needs_player_download: false,
    yoto_playlist_uri: "",
    status: "available",
    label_color: "",
    tested: false,
    notes: "",
  });

  const draftCard: PhysicalCard | null = form.card_code
    ? {
        id: 0,
        card_code: form.card_code,
        programmable_id: form.programmable_id || null,
        nfc_serial_number: form.nfc_serial_number || null,
        ndef_payload_text: form.ndef_payload_text || null,
        ndef_payload_hex: form.ndef_payload_hex || null,
        scan_source: form.scan_source || null,
        display_name: form.display_name || form.card_code,
        card_kind: form.card_kind,
        nfc_technology: form.nfc_technology || null,
        chip_type: form.chip_type || null,
        memory_size_bytes: form.memory_size_bytes ? Number(form.memory_size_bytes) : null,
        ndef_prepared: form.ndef_prepared,
        ndef_format_command: form.ndef_format_command || null,
        programming_app: form.programming_app || null,
        source_card_code: form.source_card_code || null,
        is_reusable_transfer_card: form.is_reusable_transfer_card,
        ready_to_link_in_app: form.ready_to_link_in_app,
        linked_manually: form.linked_manually,
        overwrite_ok: form.overwrite_ok,
        downloaded_to_player_confirmed: form.downloaded_to_player_confirmed,
        needs_player_download: form.needs_player_download,
        current_library_item_id: null,
        pending_job_id: null,
        yoto_playlist_uri: form.yoto_playlist_uri || null,
        status: form.status,
        label_color: form.label_color || null,
        tested: form.tested,
        last_scanned_at: null,
        last_linked_at: null,
        last_programmed_at: null,
        last_tested_at: null,
        notes: form.notes || null,
        created_at: new Date().toISOString(),
      }
    : null;

  async function refreshCards() {
    setCards(await fetchCards());
  }

  async function refreshScanDumps() {
    setScanDumps(await fetchCardScanDumps());
  }

  useEffect(() => {
    void Promise.all([refreshCards(), refreshScanDumps()]).catch((loadError) =>
      setError(loadError instanceof Error ? loadError.message : "Failed to load cards."),
    );
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (stagedDump) {
      window.localStorage.setItem(stagedCardDumpStorageKey, JSON.stringify(stagedDump));
      return;
    }
    window.localStorage.removeItem(stagedCardDumpStorageKey);
  }, [stagedDump]);

  useEffect(() => {
    if (!isNativeAndroidRuntime()) {
      return;
    }

    let cancelled = false;
    void NFC.isSupported()
      .then(({ supported }) => {
        if (!cancelled) {
          setNativeNfcSupported(supported);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setNativeNfcSupported(false);
        }
      });

    const removeReadListener = NFC.onRead((data: NDEFMessagesTransformable) => {
      const decodedPayload = data.string();
      const rawPayload = data.uint8Array();
      const firstMessage = decodedPayload.messages[0];
      const firstRawMessage = rawPayload.messages[0];
      const firstRecord = firstMessage?.records[0];
      const firstRawRecord = firstRawMessage?.records[0];
      const payloadText =
        typeof firstRecord?.payload === "string" ? firstRecord.payload.trim() : "";
      const payloadBytes =
        firstRawRecord?.payload instanceof Uint8Array ? firstRawRecord.payload : null;
      const payloadHex = payloadBytes
        ? Array.from(payloadBytes)
            .map((byte) => byte.toString(16).padStart(2, "0"))
            .join("")
        : "";
      const serialNumber = decodedPayload.tagInfo?.uid ?? "";
      const nextProgrammableId = serialNumber || payloadText;

      if (nextProgrammableId) {
        setForm((current) => ({
          ...current,
          programmable_id: nextProgrammableId,
          nfc_serial_number: serialNumber,
          ndef_payload_text: payloadText || current.ndef_payload_text,
          ndef_payload_hex: payloadHex || current.ndef_payload_hex,
          scan_source: "native_nfc",
          notes:
            current.notes ||
            (payloadText ? `Read NDEF payload: ${payloadText}` : "Read by native Android NFC."),
        }));
        setScanMessage(`Read card ${nextProgrammableId}${serialNumber ? ` via ${serialNumber}` : ""}.`);
      } else {
        setScanMessage("Card read succeeded, but no serial or payload was exposed.");
      }
      queueCardScanDump({
        scan_source: "native_nfc",
        programmable_id: nextProgrammableId || null,
        nfc_serial_number: serialNumber || null,
        ndef_payload_text: payloadText || null,
        ndef_payload_hex: payloadHex || null,
        tag_info: decodedPayload.tagInfo ? { ...decodedPayload.tagInfo } : null,
        records: decodedPayload.messages.flatMap((message, messageIndex) =>
          message.records.map((record, recordIndex) => {
            const rawRecord = rawPayload.messages[messageIndex]?.records[recordIndex];
            const rawBytes = rawRecord?.payload instanceof Uint8Array ? rawRecord.payload : null;
            return {
              type: record.type,
              payload:
                typeof record.payload === "string"
                  ? record.payload
                  : String(record.payload),
              payload_hex: rawBytes
                ? Array.from(rawBytes)
                    .map((byte) => byte.toString(16).padStart(2, "0"))
                    .join("")
                : null,
            };
          }),
        ),
      });

      setScanning(false);
      setNativeWritePending(false);
    });

    const removeErrorListener = NFC.onError((nfcError) => {
      setScanMessage(nfcError.error || "Native NFC operation failed.");
      setScanning(false);
      setNativeWritePending(false);
    });

    const removeWriteListener = NFC.onWrite(() => {
      setForm((current) => ({
        ...current,
        ndef_prepared: true,
        scan_source: current.scan_source === "manual" ? "native_nfc" : current.scan_source,
        notes: current.notes || "Wrote the current NDEF payload with native Android NFC.",
      }));
      setHelperMessage("Native NFC write completed. Re-scan the card or test it in the Yoto app.");
      setNativeWritePending(false);
      setScanning(false);
    });

    return () => {
      cancelled = true;
      removeReadListener();
      removeErrorListener();
      removeWriteListener();
    };
  }, []);

  function handleGenerateFromPlaylist() {
    setError(null);
    const generated = generatedCardPayload(form.yoto_playlist_uri);
    if (!generated.payloadText || !generated.payloadHex) {
      setHelperMessage("Enter a Yoto playlist URI first.");
      return;
    }
    setForm((current) => ({
      ...current,
      programmable_id: generated.programmableId ?? current.programmable_id,
      ndef_payload_text: generated.payloadText ?? "",
      ndef_payload_hex: generated.payloadHex ?? "",
      scan_source: current.scan_source === "manual" ? "nfc_tools" : current.scan_source,
      notes:
        current.notes ||
        `Generated manual programming payload from ${generated.programmableId ?? "playlist URI"}.`,
    }));
    setHelperMessage(`Prepared payload for ${generated.programmableId ?? generated.payloadText}.`);
  }

  async function handleCopyProgrammingValue(value: string, label: string) {
    const copied = await copyToClipboard(value);
    setHelperMessage(copied ? `Copied ${label}.` : `Clipboard copy for ${label} is not available here.`);
  }

  function queueCardScanDump(payload: {
    scan_source: string;
    programmable_id?: string | null;
    nfc_serial_number?: string | null;
    ndef_payload_text?: string | null;
    ndef_payload_hex?: string | null;
    tag_info?: Record<string, unknown> | null;
    records?: Array<Record<string, unknown>>;
  }) {
    void dumpCardScan({
      ...payload,
      runtime: currentRuntimeLabel(),
    })
      .then(() => refreshScanDumps())
      .catch((dumpError) => {
        setHelperMessage(
          dumpError instanceof Error ? `Scan dump failed: ${dumpError.message}` : "Scan dump failed.",
        );
      });
  }

  function applyScanDumpToForm(entry: CardScanDumpEntry) {
    setForm((current) => ({
      ...current,
      programmable_id: entry.programmable_id || current.programmable_id,
      nfc_serial_number: entry.nfc_serial_number || current.nfc_serial_number,
      ndef_payload_text: entry.ndef_payload_text || current.ndef_payload_text,
      ndef_payload_hex: entry.ndef_payload_hex || current.ndef_payload_hex,
      scan_source: entry.scan_source || current.scan_source,
      notes:
        current.notes ||
        `Applied captured scan dump #${entry.id} from ${entry.scan_source}.`,
    }));
    setHelperMessage(`Applied scan dump #${entry.id} to the card form.`);
  }

  function stageScanDump(entry: CardScanDumpEntry) {
    setStagedDump(entry);
    setHelperMessage(`Staged source card from scan dump #${entry.id}.`);
  }

  function clearStagedDump() {
    setStagedDump(null);
    setHelperMessage("Cleared the staged source card.");
  }

  function applyStagedDumpToForm() {
    if (!stagedDump) {
      setHelperMessage("No staged source card is loaded.");
      return;
    }
    applyScanDumpToForm(stagedDump);
  }

  async function writeScanDumpToTag(entry: CardScanDumpEntry) {
    if (!isNativeAndroidRuntime()) {
      setHelperMessage("Exact dump writes are only available in the Android app.");
      return;
    }
    if (!nativeNfcSupported) {
      setHelperMessage("Native NFC is not available on this Android device.");
      return;
    }

    const dumpRecords = entry.records
      .map((record) => {
        const type = typeof record.type === "string" ? record.type : "";
        const payloadHex = typeof record.payload_hex === "string" ? record.payload_hex : "";
        const payloadBytes = payloadHex ? hexToBytes(payloadHex) : null;
        if (!type || !payloadBytes) {
          return null;
        }
        return { type, payload: payloadBytes };
      })
      .filter((record): record is { type: string; payload: Uint8Array } => Boolean(record));

    if (dumpRecords.length === 0) {
      setHelperMessage("This scan dump does not include raw record bytes yet. Re-scan with the updated app first.");
      return;
    }

    setError(null);
    setScanning(true);
    setNativeWritePending(true);
    setScanMessage(`Hold the new card against the phone to write scan dump #${entry.id}.`);

    try {
      await NFC.writeNDEF({
        rawMode: true,
        records: dumpRecords,
      });
    } catch (writeError) {
      setNativeWritePending(false);
      setScanning(false);
      setHelperMessage(writeError instanceof Error ? writeError.message : "Could not write stored scan dump.");
    }
  }

  async function writeStagedDumpToTag() {
    if (!stagedDump) {
      setHelperMessage("No staged source card is loaded.");
      return;
    }
    await writeScanDumpToTag(stagedDump);
  }

  async function handleNativeScanCard() {
    setError(null);
    setHelperMessage(null);
    setScanMessage(null);

    if (!nativeNfcSupported) {
      setScanMessage("Native NFC is not available on this Android device.");
      return;
    }

    setScanning(true);
    setNativeWritePending(false);
    setScanMessage("Hold the card against the phone.");

    try {
      await NFC.startScan();
    } catch (scanError) {
      setScanning(false);
      setScanMessage(scanError instanceof Error ? scanError.message : "Could not start native NFC scan.");
    }
  }

  async function handleNativeWriteCard() {
    setError(null);
    setHelperMessage(null);
    setScanMessage(null);

    if (!nativeNfcSupported) {
      setHelperMessage("Native NFC is not available on this Android device.");
      return;
    }

    const payloadBytes = form.ndef_payload_hex ? hexToBytes(form.ndef_payload_hex) : null;
    if (form.ndef_payload_hex && !payloadBytes) {
      setHelperMessage("NDEF payload hex is invalid. Use an even number of hex characters.");
      return;
    }
    if (!payloadBytes && !form.ndef_payload_text) {
      setHelperMessage("Prepare an NDEF payload first.");
      return;
    }

    setScanning(true);
    setNativeWritePending(true);
    setScanMessage("Hold the card against the phone to write the prepared payload.");

    try {
      await NFC.writeNDEF({
        rawMode: true,
        records: [
          {
            type: "custom",
            payload: payloadBytes ?? new TextEncoder().encode(form.ndef_payload_text),
          },
        ],
      });
    } catch (writeError) {
      setNativeWritePending(false);
      setScanning(false);
      setHelperMessage(writeError instanceof Error ? writeError.message : "Could not start native NFC write.");
    }
  }

  async function startWebNfcScan(promptOnly: boolean) {
    setError(null);
    setScanMessage(null);
    if (!isWebNfcAvailable()) {
      setScanMessage(
        "Web NFC is not available in this browser. Enter the card ID manually or use NFC Tools.",
      );
      return;
    }

    setScanning(true);
    try {
      const reader = new window.NDEFReader();
      await reader.scan();
      if (promptOnly) {
        setScanMessage("NFC permission request completed. If Android allowed it, try Scan with phone now.");
        setScanning(false);
        return;
      }
      setScanMessage("Hold the card against the phone.");
      reader.onreading = (event) => {
        const readingEvent = event as NdefReadingEvent;
        const serialNumber = readingEvent.serialNumber || "";
        const decodedPayload = decodeNdefRecords(readingEvent.message.records);
        const payloadText = decodedPayload.text || "";
        const nextProgrammableId = serialNumber || payloadText;
        if (nextProgrammableId) {
          setForm((current) => ({
            ...current,
            programmable_id: nextProgrammableId,
            nfc_serial_number: serialNumber,
            ndef_payload_text: payloadText,
            ndef_payload_hex: decodedPayload.hex || current.ndef_payload_hex,
            scan_source: "web_nfc",
            notes: current.notes || (payloadText ? `Read NDEF payload: ${payloadText}` : "Read by Android Web NFC."),
          }));
          setScanMessage(`Read card ${nextProgrammableId}${serialNumber ? ` via ${serialNumber}` : ""}.`);
        } else {
          setScanMessage("Card read succeeded, but no serial or payload was exposed.");
        }
        queueCardScanDump({
          scan_source: "web_nfc",
          programmable_id: nextProgrammableId || null,
          nfc_serial_number: serialNumber || null,
          ndef_payload_text: payloadText || null,
          ndef_payload_hex: decodedPayload.hex || null,
          tag_info: {
            record_count: readingEvent.message.records.length,
          },
          records: readingEvent.message.records.map((record, index) => ({
            index,
            has_data: Boolean(record.data),
            payload_hex: record.data ? normaliseRecordData(record.data).reduce((all, byte) => all + byte.toString(16).padStart(2, "0"), "") : null,
          })),
        });
        setScanning(false);
      };
      reader.onerror = () => {
        setScanMessage("The NFC read failed. Try again or capture the value from NFC Tools.");
        setScanning(false);
        };
    } catch (scanError) {
      setScanning(false);
      setScanMessage(formatNfcScanError(scanError));
    }
  }

  async function handleRequestNfcPermission() {
    if (isNativeAndroidRuntime()) {
      await handleNativeScanCard();
      return;
    }
    await startWebNfcScan(true);
  }

  async function handleScanCard() {
    if (isNativeAndroidRuntime()) {
      await handleNativeScanCard();
      return;
    }
    await startWebNfcScan(false);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createCard({
        card_code: form.card_code,
        programmable_id: form.programmable_id || null,
        nfc_serial_number: form.nfc_serial_number || null,
        ndef_payload_text: form.ndef_payload_text || null,
        ndef_payload_hex: form.ndef_payload_hex || null,
        scan_source: form.scan_source || null,
        display_name: form.display_name,
        card_kind: form.card_kind,
        nfc_technology: form.nfc_technology || null,
        chip_type: form.chip_type || null,
        memory_size_bytes: form.memory_size_bytes ? Number(form.memory_size_bytes) : null,
        ndef_prepared: form.ndef_prepared,
        ndef_format_command: form.ndef_format_command || null,
        programming_app: form.programming_app || null,
        source_card_code: form.source_card_code || null,
        is_reusable_transfer_card: form.is_reusable_transfer_card,
        ready_to_link_in_app: form.ready_to_link_in_app,
        linked_manually: form.linked_manually,
        overwrite_ok: form.overwrite_ok,
        downloaded_to_player_confirmed: form.downloaded_to_player_confirmed,
        needs_player_download: form.needs_player_download,
        yoto_playlist_uri: form.yoto_playlist_uri || null,
        status: form.status,
        label_color: form.label_color || null,
        tested: form.tested,
        notes: form.notes || null,
      });
      setForm((current) => ({
        ...current,
        card_code: "",
        programmable_id: "",
        nfc_serial_number: "",
        ndef_payload_text: "",
        ndef_payload_hex: "",
        scan_source: "manual",
        display_name: "",
        source_card_code: "",
        yoto_playlist_uri: "",
        label_color: "",
        tested: false,
        ready_to_link_in_app: false,
        linked_manually: false,
        overwrite_ok: false,
        downloaded_to_player_confirmed: false,
        needs_player_download: false,
        notes: "",
      }));
      await refreshCards();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Card creation failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Cards</p>
          <h2>Android card console</h2>
        </div>
        <span className="status-pill">{cards.length} cards</span>
      </div>

      <div className="card-console-grid">
        <article className="card-console-panel">
          <div>
            <p className="eyebrow">Step 1</p>
            <h3>Read or prepare a card</h3>
            <p className="muted">
              Use native NFC inside the Android app when available. Keep the manual NFC Tools path
              visible so tags can still be captured or reprogrammed when device NFC behaves
              differently.
            </p>
          </div>
          <div className="card-console-actions">
            <button
              className="secondary-button"
              disabled={scanning}
              onClick={() => void handleRequestNfcPermission()}
              type="button"
            >
              {isNativeAndroidRuntime() ? "Prime native NFC" : "Request NFC permission"}
            </button>
            <button className="primary-button" disabled={scanning} onClick={() => void handleScanCard()} type="button">
              {scanning ? "Scanning" : "Scan with phone"}
            </button>
            <button
              className="secondary-button"
              disabled={scanning || !isNativeAndroidRuntime()}
              onClick={() => void handleNativeWriteCard()}
              type="button"
            >
              {nativeWritePending ? "Writing tag" : "Write payload to tag"}
            </button>
            <span className="status-pill status-pill-muted">
              {isNativeAndroidRuntime()
                ? nativeNfcSupported
                  ? "Native NFC ready"
                  : "Native NFC unavailable"
                : isWebNfcAvailable()
                  ? "Web NFC available"
                  : "Manual capture"}
            </span>
          </div>
          {scanMessage ? <p className="muted">{scanMessage}</p> : null}
          {helperMessage ? <p className="muted">{helperMessage}</p> : null}
          <p className="muted">
            Capture the serial, decoded payload, and raw payload bytes separately so copied cards
            and manual programming remain auditable.
          </p>
          {isAndroidAppRuntime() ? (
            <p className="muted">
              Android app note: the app now prefers a native Capacitor NFC plugin. Chrome may still
              behave differently because it uses Web NFC instead of the native plugin path.
            </p>
          ) : null}
        </article>
        <article className="card-console-panel">
          <p className="eyebrow">Workflow</p>
          <CardWorkflowChecklist card={draftCard} />
        </article>
      </div>

      <section className="card-console-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Scan Dumps</p>
            <h3>Recent captured tags</h3>
          </div>
          <div className="button-row">
            <button className="secondary-button" onClick={() => void refreshScanDumps()} type="button">
              Refresh dumps
            </button>
            <span className="status-pill status-pill-muted">{scanDumps.length} stored</span>
          </div>
        </div>
        {scanDumps.length === 0 ? (
          <p className="muted">No persisted scan dumps yet. Scan a card in the app to capture one.</p>
        ) : (
          <div className="compact-list">
            {scanDumps.map((entry) => (
              <article className="tag-row" key={entry.id}>
                <div>
                  <strong>#{entry.id}</strong>{" "}
                  <span className="muted">
                    {entry.scan_source} {entry.nfc_serial_number ? `· ${entry.nfc_serial_number}` : ""}
                  </span>
                  <p className="muted">
                    {entry.ndef_payload_text || entry.programmable_id || "No text payload captured"}
                  </p>
                </div>
                <div className="button-row">
                  <button
                    className="secondary-button"
                    onClick={() => stageScanDump(entry)}
                    type="button"
                  >
                    Stage source card
                  </button>
                  <button
                    className="secondary-button"
                    onClick={() => applyScanDumpToForm(entry)}
                    type="button"
                  >
                    Apply to form
                  </button>
                  <button
                    className="secondary-button"
                    disabled={!entry.ndef_payload_text}
                    onClick={() =>
                      void handleCopyProgrammingValue(entry.ndef_payload_text ?? "", "captured payload text")
                    }
                    type="button"
                  >
                    Copy text
                  </button>
                  <button
                    className="secondary-button"
                    disabled={!entry.ndef_payload_hex}
                    onClick={() =>
                      void handleCopyProgrammingValue(entry.ndef_payload_hex ?? "", "captured payload hex")
                    }
                    type="button"
                  >
                    Copy hex
                  </button>
                  <button
                    className="secondary-button"
                    disabled={!isNativeAndroidRuntime() || scanning}
                    onClick={() => void writeScanDumpToTag(entry)}
                    type="button"
                  >
                    Write this dump
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="card-console-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Staged Copy</p>
            <h3>Source card to blank card flow</h3>
          </div>
          <div className="button-row">
            <button
              className="secondary-button"
              disabled={!stagedDump}
              onClick={() => applyStagedDumpToForm()}
              type="button"
            >
              Apply staged to form
            </button>
            <button
              className="secondary-button"
              disabled={!stagedDump || !isNativeAndroidRuntime() || scanning}
              onClick={() => void writeStagedDumpToTag()}
              type="button"
            >
              {nativeWritePending ? "Writing staged card" : "Write staged card to blank tag"}
            </button>
            <button
              className="secondary-button"
              disabled={!stagedDump}
              onClick={() => clearStagedDump()}
              type="button"
            >
              Clear staged
            </button>
          </div>
        </div>
        {stagedDump ? (
          <div className="compact-list">
            <p className="muted">
              Staged source: #{stagedDump.id} {stagedDump.nfc_serial_number ?? "unknown UID"} · {stagedDump.scan_source}
            </p>
            <p className="muted">
              Payload: {stagedDump.ndef_payload_text ?? stagedDump.programmable_id ?? "No text payload captured"}
            </p>
            <p className="muted">
              Reddit workflow fit: prepare blank 48-byte MIFARE Ultralight EV1 once, then write the staged source dump to the new card.
            </p>
          </div>
        ) : (
          <p className="muted">
            Stage a captured genuine MYO/source card from the list below, then write that staged data to a prepared blank card.
          </p>
        )}
      </section>

      <form className="import-form" onSubmit={(event) => void handleSubmit(event)}>
        <div className="import-grid import-grid-wide">
          <label>
            Card ID
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, card_code: event.target.value.toUpperCase() }))
              }
              pattern="[A-Za-z0-9]+"
              placeholder="CARD01"
              required
              value={form.card_code}
            />
          </label>
          <label>
            Programmable ID
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, programmable_id: event.target.value }))
              }
              placeholder="04A1B2C3D4"
              value={form.programmable_id}
            />
          </label>
          <label>
            NFC serial
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, nfc_serial_number: event.target.value.toUpperCase() }))
              }
              placeholder="04A1B2C3D4"
              value={form.nfc_serial_number}
            />
          </label>
          <label>
            Name
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, display_name: event.target.value }))
              }
              placeholder="Card 01"
              required
              value={form.display_name}
            />
          </label>
        </div>

        <div className="import-grid import-grid-wide">
          <label>
            Kind
            <select
              onChange={(event) =>
                setForm((current) => ({ ...current, card_kind: event.target.value }))
              }
              value={form.card_kind}
            >
              <option value="official_myo">Official MYO</option>
              <option value="generic_mifare_ultralight_ev1">Generic MIFARE Ultralight EV1</option>
              <option value="other_nfc">Other NFC</option>
            </select>
          </label>
          <label>
            NFC technology
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, nfc_technology: event.target.value }))
              }
              value={form.nfc_technology}
            />
          </label>
        </div>

        <div className="import-grid import-grid-wide">
          <label>
            Chip
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, chip_type: event.target.value }))
              }
              value={form.chip_type}
            />
          </label>
          <label>
            Memory bytes
            <input
              min="1"
              onChange={(event) =>
                setForm((current) => ({ ...current, memory_size_bytes: event.target.value }))
              }
              type="number"
              value={form.memory_size_bytes}
            />
          </label>
          <label>
            Programming app
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, programming_app: event.target.value }))
              }
              value={form.programming_app}
            />
          </label>
          <label>
            Scan source
            <select
              onChange={(event) =>
                setForm((current) => ({ ...current, scan_source: event.target.value }))
              }
              value={form.scan_source}
            >
              <option value="manual">Manual entry</option>
              <option value="native_nfc">Native Android NFC</option>
              <option value="web_nfc">Android Web NFC</option>
              <option value="nfc_tools">NFC Tools</option>
              <option value="transfer_card">Transfer card copy</option>
            </select>
          </label>
        </div>

        <div className="import-grid import-grid-wide">
          <label>
            Source card
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, source_card_code: event.target.value.toUpperCase() }))
              }
              placeholder="MYOTRANSFER01"
              value={form.source_card_code}
            />
          </label>
          <label>
            Playlist URI
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, yoto_playlist_uri: event.target.value }))
              }
              placeholder="yoto://playlist/..."
              value={form.yoto_playlist_uri}
            />
          </label>
          <div className="helper-action-group">
            <button className="secondary-button" onClick={() => handleGenerateFromPlaylist()} type="button">
              Generate programming payload
            </button>
            <button
              className="secondary-button"
              disabled={!isNativeAndroidRuntime() || scanning || (!form.ndef_payload_text && !form.ndef_payload_hex)}
              onClick={() => void handleNativeWriteCard()}
              type="button"
            >
              Write payload natively
            </button>
          </div>
          <label>
            Status
            <select
              onChange={(event) =>
                setForm((current) => ({ ...current, status: event.target.value }))
              }
              value={form.status}
            >
              <option value="available">Available</option>
              <option value="ready_to_link">Ready to link</option>
              <option value="linked">Linked</option>
              <option value="needs_attention">Needs attention</option>
            </select>
          </label>
        </div>

        <div className="import-grid">
          <label>
            NDEF command
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, ndef_format_command: event.target.value }))
              }
              value={form.ndef_format_command}
            />
          </label>
          <div className="helper-action-group">
            <button
              className="secondary-button"
              disabled={!form.ndef_payload_text}
              onClick={() => void handleCopyProgrammingValue(form.ndef_payload_text, "NDEF payload text")}
              type="button"
            >
              Copy text
            </button>
            <button
              className="secondary-button"
              disabled={!form.ndef_payload_hex}
              onClick={() => void handleCopyProgrammingValue(form.ndef_payload_hex, "NDEF payload hex")}
              type="button"
            >
              Copy hex
            </button>
          </div>
          <label>
            NDEF payload text
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, ndef_payload_text: event.target.value }))
              }
              value={form.ndef_payload_text}
            />
          </label>
          <label>
            NDEF payload hex
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, ndef_payload_hex: event.target.value }))
              }
              value={form.ndef_payload_hex}
            />
          </label>
        </div>

        <div className="import-grid">
          <label>
            Label colour
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, label_color: event.target.value }))
              }
              value={form.label_color}
            />
          </label>
          <label>
            Notes
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, notes: event.target.value }))
              }
              value={form.notes}
            />
          </label>
        </div>

        <div className="checkbox-pair">
          <label className="checkbox-row">
            <input
              checked={form.ndef_prepared}
              onChange={(event) =>
                setForm((current) => ({ ...current, ndef_prepared: event.target.checked }))
              }
              type="checkbox"
            />
            NDEF prepared
          </label>
          <label className="checkbox-row">
            <input
              checked={form.tested}
              onChange={(event) =>
                setForm((current) => ({ ...current, tested: event.target.checked }))
              }
              type="checkbox"
            />
            Tested
          </label>
          <label className="checkbox-row">
            <input
              checked={form.is_reusable_transfer_card}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  is_reusable_transfer_card: event.target.checked,
                }))
              }
              type="checkbox"
            />
            Reusable transfer card
          </label>
          <label className="checkbox-row">
            <input
              checked={form.ready_to_link_in_app}
              onChange={(event) =>
                setForm((current) => ({ ...current, ready_to_link_in_app: event.target.checked }))
              }
              type="checkbox"
            />
            Ready to link in app
          </label>
          <label className="checkbox-row">
            <input
              checked={form.linked_manually}
              onChange={(event) =>
                setForm((current) => ({ ...current, linked_manually: event.target.checked }))
              }
              type="checkbox"
            />
            Linked manually
          </label>
          <label className="checkbox-row">
            <input
              checked={form.overwrite_ok}
              onChange={(event) =>
                setForm((current) => ({ ...current, overwrite_ok: event.target.checked }))
              }
              type="checkbox"
            />
            OK to overwrite
          </label>
          <label className="checkbox-row">
            <input
              checked={form.needs_player_download}
              onChange={(event) =>
                setForm((current) => ({ ...current, needs_player_download: event.target.checked }))
              }
              type="checkbox"
            />
            Needs player download
          </label>
          <label className="checkbox-row">
            <input
              checked={form.downloaded_to_player_confirmed}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  downloaded_to_player_confirmed: event.target.checked,
                }))
              }
              type="checkbox"
            />
            Download confirmed
          </label>
        </div>

        <div className="form-actions">
          <span className="muted">Alphanumeric card IDs only</span>
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "Adding" : "Add card"}
          </button>
        </div>
      </form>
      {error ? <p className="auth-error">{error}</p> : null}

      <div className="item-list">
        {cards.length === 0 ? (
          <EmptyState message="No cards yet." />
        ) : (
          cards.map((card) => (
            <article className="list-row" key={card.id}>
              <div>
                <h3>
                  <Link to={`/cards/${card.id}`}>{card.display_name}</Link>
                </h3>
                <p className="muted">
                  {card.card_code} · {card.card_kind} · {card.status}
                </p>
                <p className="muted">
                  {card.programmable_id ?? "No programmable ID"} ·{" "}
                  {card.chip_type ?? "Chip unknown"} ·{" "}
                  {card.memory_size_bytes ? `${card.memory_size_bytes} bytes` : "Memory unknown"}
                </p>
              </div>
              <div className="row-actions">
                {card.ndef_prepared ? <span className="status-pill">NDEF</span> : null}
                {card.ready_to_link_in_app ? <span className="status-pill">Ready</span> : null}
                {card.linked_manually ? <span className="status-pill">Linked</span> : null}
                {card.needs_player_download ? (
                  <span className="status-pill status-pill-muted">Needs download</span>
                ) : null}
                {card.tested ? <span className="status-pill status-pill-muted">Tested</span> : null}
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

function CardDetailPage() {
  const { cardId } = useParams();
  const numericCardId = Number(cardId);
  const [card, setCard] = useState<PhysicalCard | null>(null);
  const [history, setHistory] = useState<CardAssignmentEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshCardPage() {
    if (!Number.isFinite(numericCardId)) {
      throw new Error("Invalid card.");
    }
    const [nextCard, nextHistory] = await Promise.all([fetchCard(numericCardId), fetchCardHistory(numericCardId)]);
    setCard(nextCard);
    setHistory(nextHistory);
  }

  useEffect(() => {
    if (!Number.isFinite(numericCardId)) {
      setError("Invalid card.");
      setLoading(false);
      return;
    }
    setLoading(true);
    void refreshCardPage()
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "Failed to load card."),
      )
      .finally(() => setLoading(false));
  }, [numericCardId]);

  async function handleCardWorkflowAction(
    payload: Parameters<typeof updateCard>[1],
    successMessage: string,
  ) {
    if (!card) {
      return;
    }
    setError(null);
    setActionMessage(null);
    try {
      await updateCard(card.id, payload);
      await refreshCardPage();
      setActionMessage(successMessage);
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Failed to update card.");
    }
  }

  async function handleApplyPlaylistProgramming() {
    if (!card?.yoto_playlist_uri) {
      setActionMessage("This card does not have a Yoto playlist URI yet.");
      return;
    }
    const generated = generatedCardPayload(card.yoto_playlist_uri);
    await handleCardWorkflowAction(
      {
        programmable_id: generated.programmableId,
        ndef_payload_text: generated.payloadText,
        ndef_payload_hex: generated.payloadHex,
        scan_source: card.scan_source ?? "nfc_tools",
        ndef_prepared: true,
        notes: card.notes ?? "Generated programming payload from the saved Yoto playlist URI.",
      },
      "Applied generated programming payload from the saved playlist URI.",
    );
  }

  async function handleCopyCardValue(value: string | null, label: string) {
    const copied = await copyToClipboard(value ?? "");
    setActionMessage(copied ? `Copied ${label}.` : `Clipboard copy for ${label} is not available here.`);
  }

  if (loading) {
    return (
      <section className="panel">
        <p className="eyebrow">Cards</p>
        <h2>Loading card</h2>
      </section>
    );
  }

  if (error || !card) {
    return (
      <section className="panel">
        <p className="eyebrow">Cards</p>
        <h2>Card detail</h2>
        <p className="auth-error">{error ?? "Card not found."}</p>
      </section>
    );
  }

  const cardSteps = cardWorkflowSteps(card);
  const cardSummary = workflowStatusSummary(cardSteps);

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Card</p>
          <h2>{card.display_name}</h2>
          <p className="muted">
            {card.card_code} · {card.card_kind} · {card.status}
          </p>
        </div>
        <Link className="secondary-button" to="/cards">
          Back to cards
        </Link>
      </div>

      <div className="detail-grid">
        <article className="detail-block workflow-overview-card">
          <h3>{cardSummary.title}</h3>
          <p className="muted">{cardSummary.detail}</p>
          <WorkflowChecklist steps={cardSteps} />
        </article>
        <article className="detail-block">
          <h3>Identifiers</h3>
          <p className="muted">Programmable ID: {card.programmable_id ?? "Not recorded"}</p>
          <p className="muted">Playlist URI: {card.yoto_playlist_uri ?? "Not linked"}</p>
          <p className="muted">
            Current library item: {card.current_library_item_id ?? "None"} · Pending job:{" "}
            {card.pending_job_id ?? "None"}
          </p>
        </article>
        <article className="detail-block">
          <h3>NFC details</h3>
          <p className="muted">{card.nfc_technology ?? "NFC technology unknown"}</p>
          <p className="muted">
            {card.chip_type ?? "Chip unknown"} ·{" "}
            {card.memory_size_bytes ? `${card.memory_size_bytes} bytes` : "Memory unknown"}
          </p>
          <p className="muted">Programming app: {card.programming_app ?? "Not recorded"}</p>
          <div className="inline-link-panel">
            <p className="muted">Payload text: {card.ndef_payload_text ?? "Not recorded"}</p>
            <p className="muted">Payload hex: {card.ndef_payload_hex ?? "Not recorded"}</p>
            <div className="button-row">
              <button
                className="secondary-button"
                disabled={!card.ndef_payload_text}
                onClick={() => void handleCopyCardValue(card.ndef_payload_text, "payload text")}
                type="button"
              >
                Copy payload text
              </button>
              <button
                className="secondary-button"
                disabled={!card.ndef_payload_hex}
                onClick={() => void handleCopyCardValue(card.ndef_payload_hex, "payload hex")}
                type="button"
              >
                Copy payload hex
              </button>
            </div>
          </div>
        </article>
        <article className="detail-block">
          <h3>Workflow</h3>
          <div className="tag-chip-row">
            {card.ndef_prepared ? <span className="status-pill">NDEF prepared</span> : null}
            {card.ready_to_link_in_app ? <span className="status-pill">Ready to link</span> : null}
            {card.linked_manually ? <span className="status-pill">Linked manually</span> : null}
            {card.overwrite_ok ? <span className="status-pill">Overwrite OK</span> : null}
            {card.needs_player_download ? <span className="status-pill">Needs download</span> : null}
            {card.downloaded_to_player_confirmed ? <span className="status-pill">Downloaded</span> : null}
            {card.tested ? <span className="status-pill status-pill-muted">Tested</span> : null}
          </div>
          <div className="button-row">
            <button className="secondary-button" onClick={() => void handleApplyPlaylistProgramming()} type="button">
              Apply playlist payload
            </button>
            <button
              className="secondary-button"
              onClick={() =>
                void handleCardWorkflowAction(
                  { ndef_prepared: true, status: card.status === "available" ? "ready_to_link" : card.status },
                  "Marked the card as NDEF prepared.",
                )
              }
              type="button"
            >
              Mark NDEF ready
            </button>
            <button
              className="secondary-button"
              onClick={() =>
                void handleCardWorkflowAction(
                  { linked_manually: true, ready_to_link_in_app: true, status: "linked" },
                  "Marked the card as linked in Yoto.",
                )
              }
              type="button"
            >
              Mark linked
            </button>
            <button
              className="secondary-button"
              onClick={() =>
                void handleCardWorkflowAction(
                  { downloaded_to_player_confirmed: true, needs_player_download: false },
                  "Marked the player download as confirmed.",
                )
              }
              type="button"
            >
              Confirm download
            </button>
            <button
              className="secondary-button"
              onClick={() => void handleCardWorkflowAction({ tested: true }, "Marked playback as tested.")}
              type="button"
            >
              Mark tested
            </button>
          </div>
        </article>
        <article className="detail-block">
          <h3>Notes</h3>
          <p className="muted">{card.notes ?? "No notes recorded."}</p>
          <p className="muted">Source card: {card.source_card_code ?? "None"}</p>
          <p className="muted">Reusable transfer card: {card.is_reusable_transfer_card ? "Yes" : "No"}</p>
        </article>
      </div>
      {actionMessage ? <p className="muted">{actionMessage}</p> : null}

      <div className="detail-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">History</p>
            <h2>Assignment history</h2>
          </div>
          <span className="status-pill">{history.length} events</span>
        </div>
        {history.length === 0 ? (
          <EmptyState message="No assignment history yet." />
        ) : (
          <div className="compact-table">
            {history.map((event) => (
              <div className="compact-table-row" key={event.id}>
                <span className="status-pill status-pill-muted">{event.event_type}</span>
                <div>
                  <strong>{event.summary}</strong>
                  <p className="muted">
                    Library item {event.previous_library_item_id ?? "none"} to{" "}
                    {event.library_item_id ?? "none"} · Job {event.job_id ?? "none"}
                  </p>
                  <p className="muted">
                    {event.previous_status ?? "none"} to {event.new_status ?? "none"} ·{" "}
                    {new Date(event.created_at).toLocaleString()}
                  </p>
                </div>
                <span className="muted">{event.yoto_playlist_uri ?? "No playlist URI"}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [yotoCredential, setYotoCredential] = useState<YotoCredentialStatus | null>(null);
  const [yotoAccountLabel, setYotoAccountLabel] = useState("Household Yoto");
  const [preparedAuthUrl, setPreparedAuthUrl] = useState<string | null>(null);
  const [yotoProbe, setYotoProbe] = useState<YotoCredentialProbeResponse | null>(null);
  const [yotoDebugResult, setYotoDebugResult] = useState<YotoApiDebugResponse | null>(null);
  const [yotoDebugHistory, setYotoDebugHistory] = useState<YotoApiDebugResponse[]>([]);
  const [customDebugMethod, setCustomDebugMethod] = useState<"GET" | "POST" | "PUT" | "PATCH" | "DELETE">("GET");
  const [customDebugPath, setCustomDebugPath] = useState("/content/mine?showdeleted=false");
  const [customDebugBody, setCustomDebugBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void Promise.all([fetchSettings(), fetchYotoCredentialStatus()])
      .then(([nextSettings, nextCredential]) => {
        setSettings(nextSettings);
        setYotoCredential(nextCredential);
        setYotoAccountLabel(nextCredential.account_label);
        setPreparedAuthUrl(nextCredential.authorization_url);
      })
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "Failed to load settings."),
      );
  }, []);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      setSettings(await updateSettings(settings));
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  async function handlePrepareYotoOAuth() {
    setSaving(true);
    setError(null);
    setYotoProbe(null);
    setYotoDebugResult(null);
    try {
      const pkce = await createPkcePair();
      const result = await startYotoOAuth(yotoAccountLabel, pkce.challenge);
      setYotoCredential(result.credential);
      setPreparedAuthUrl(result.authorization_url);
      window.sessionStorage.setItem(
        yotoPkceStorageKey,
        JSON.stringify({ verifier: pkce.verifier, state: result.oauth_state }),
      );
      window.location.href = result.authorization_url;
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Failed to prepare Yoto OAuth.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDisconnectYoto() {
    setSaving(true);
    setError(null);
    try {
      const result = await disconnectYotoCredentials();
      setYotoCredential(result);
      setPreparedAuthUrl(null);
      setYotoProbe(null);
      setYotoDebugResult(null);
    } catch (disconnectError) {
      setError(disconnectError instanceof Error ? disconnectError.message : "Failed to disconnect Yoto.");
    } finally {
      setSaving(false);
    }
  }

  async function handleProbeYoto() {
    setSaving(true);
    setError(null);
    try {
      const result = await probeYotoCredentials();
      setYotoCredential(result.credential);
      setYotoProbe(result);
      setYotoDebugResult(null);
    } catch (probeError) {
      setError(probeError instanceof Error ? probeError.message : "Failed to probe the Yoto API.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDebugRequest(config: {
    label?: string | null;
    method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    path: string;
    body_json?: string | null;
  }) {
    setSaving(true);
    setError(null);
    try {
      const result = await debugYotoApiRequest(config);
      setYotoCredential(result.credential);
      setYotoDebugResult(result);
      setYotoDebugHistory((current) => [result, ...current].slice(0, 8));
    } catch (debugError) {
      setError(debugError instanceof Error ? debugError.message : "Failed to send the Yoto API request.");
    } finally {
      setSaving(false);
    }
  }

  async function handleCustomDebugRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await handleDebugRequest({
      method: customDebugMethod,
      path: customDebugPath,
      body_json: customDebugBody.trim() || null,
    });
  }

  if (!settings) {
    return (
      <section className="panel">
        <p className="eyebrow">Settings</p>
        <h2>Processing defaults</h2>
        {error ? (
          <p className="auth-error">{error}</p>
        ) : (
          <EmptyState message="Loading settings..." />
        )}
      </section>
    );
  }

  return (
    <section className="panel">
      <p className="eyebrow">Settings</p>
      <h2>Processing defaults</h2>
      <form className="data-form" onSubmit={(event) => void handleSave(event)}>
        <label>
          Target duration hours
          <input
            min="0"
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, target_duration_hours: Number(event.target.value) } : current,
              )
            }
            step="0.1"
            type="number"
            value={settings.target_duration_hours}
          />
        </label>
        <label>
          Target size MB
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, target_size_mb: Number(event.target.value) } : current,
              )
            }
            type="number"
            value={settings.target_size_mb}
          />
        </label>
        <label>
          Audiobook bitrate kbps
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, audiobook_bitrate_kbps: Number(event.target.value) } : current,
              )
            }
            type="number"
            value={settings.audiobook_bitrate_kbps}
          />
        </label>
        <label>
          Music bitrate kbps
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, music_bitrate_kbps: Number(event.target.value) } : current,
              )
            }
            type="number"
            value={settings.music_bitrate_kbps}
          />
        </label>
        <label className="checkbox-row">
          <input
            checked={settings.normalise_loudness_default}
            onChange={(event) =>
              setSettings((current) =>
                current
                  ? { ...current, normalise_loudness_default: event.target.checked }
                  : current,
              )
            }
            type="checkbox"
          />
          Normalise loudness by default
        </label>

        <h3 className="settings-section-title">Yoto API</h3>
        <label className="checkbox-row">
          <input
            checked={settings.yoto_api_enabled}
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, yoto_api_enabled: event.target.checked } : current,
              )
            }
            type="checkbox"
          />
          Enable Yoto API integration
        </label>
        <label>
          API base URL
          <input
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, yoto_api_base_url: event.target.value } : current,
              )
            }
            type="url"
            value={settings.yoto_api_base_url}
          />
        </label>
        <label>
          Auth base URL
          <input
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, yoto_auth_base_url: event.target.value } : current,
              )
            }
            type="url"
            value={settings.yoto_auth_base_url}
          />
        </label>
        <label>
          Client ID
          <input
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, yoto_client_id: event.target.value } : current,
              )
            }
            value={settings.yoto_client_id}
          />
        </label>
        <label>
          Redirect URI
          <input
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, yoto_redirect_uri: event.target.value } : current,
              )
            }
            value={settings.yoto_redirect_uri}
          />
        </label>
        <label>
          OAuth scope
          <input
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, yoto_oauth_scope: event.target.value } : current,
              )
            }
            value={settings.yoto_oauth_scope}
          />
        </label>
        <label>
          Upload timeout seconds
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current
                  ? { ...current, yoto_upload_timeout_seconds: Number(event.target.value) }
                  : current,
              )
            }
            type="number"
            value={settings.yoto_upload_timeout_seconds}
          />
        </label>
        <label>
          Transcode poll seconds
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current
                  ? { ...current, yoto_transcode_poll_seconds: Number(event.target.value) }
                  : current,
              )
            }
            type="number"
            value={settings.yoto_transcode_poll_seconds}
          />
        </label>
        <label>
          Transcode timeout minutes
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current
                  ? { ...current, yoto_transcode_timeout_minutes: Number(event.target.value) }
                  : current,
              )
            }
            type="number"
            value={settings.yoto_transcode_timeout_minutes}
          />
        </label>
        <p className="settings-note">
          Store refresh tokens and client secrets in Kubernetes Secrets, not application settings.
        </p>
        <div className="settings-connection-panel">
          <div>
            <h3 className="settings-section-title">Yoto connection</h3>
            <p className="settings-note">
              Status: {yotoCredential?.status ?? "loading"} · Live API call: no
            </p>
          </div>
          <label>
            Account label
            <input
              onChange={(event) => setYotoAccountLabel(event.target.value)}
              value={yotoAccountLabel}
            />
          </label>
          <div className="button-row">
            <button
              className="secondary-button"
              disabled={saving}
              onClick={() => void handlePrepareYotoOAuth()}
              type="button"
            >
              Test browser auth
            </button>
            <button
              className="secondary-button"
              disabled={saving || !yotoCredential?.token_storage_ref}
              onClick={() => void handleProbeYoto()}
              type="button"
            >
              Probe live API
            </button>
            <button
              className="secondary-button"
              disabled={saving || !yotoCredential?.id}
              onClick={() => void handleDisconnectYoto()}
              type="button"
            >
              Disconnect locally
            </button>
          </div>
          {preparedAuthUrl ? (
            <p className="settings-note auth-url-break">
              Last auth URL: <a href={preparedAuthUrl}>{preparedAuthUrl}</a>
            </p>
          ) : yotoCredential?.token_storage_ref ? (
            <p className="settings-note">
              Credential is connected. Re-run browser auth after changing scopes or redirect settings.
            </p>
          ) : (
            <p className="settings-note">
              Set the client ID and redirect URI, save settings, then test browser auth.
            </p>
          )}
          {yotoCredential?.error_summary ? (
            <p className="settings-note">{yotoCredential.error_summary}</p>
          ) : null}
          {yotoProbe ? (
            <div className="settings-note">
              <p>
                Probe: {yotoProbe.probe_label}
                {yotoProbe.http_status ? ` (${yotoProbe.http_status})` : ""}
                {yotoProbe.token_refreshed ? " · token refreshed" : ""}
              </p>
              {yotoProbe.probe_url ? <p>URL: {yotoProbe.probe_url}</p> : null}
              {yotoProbe.response_excerpt ? <pre>{yotoProbe.response_excerpt}</pre> : null}
              {yotoProbe.error_detail && yotoProbe.error_detail !== yotoProbe.response_excerpt ? (
                <pre>{yotoProbe.error_detail}</pre>
              ) : null}
            </div>
          ) : null}
          <div className="yoto-explorer-grid">
            {yotoDebugPresets.map((preset) => (
              <button
                key={`${preset.method}:${preset.path}`}
                className="secondary-button yoto-explorer-card"
                disabled={saving || !yotoCredential?.token_storage_ref}
                onClick={() =>
                  void handleDebugRequest({
                    label: preset.label,
                    method: preset.method,
                    path: preset.path,
                  })
                }
                type="button"
              >
                <strong>{preset.label}</strong>
                <span>{preset.method}</span>
                <span>{preset.path}</span>
              </button>
            ))}
          </div>
          <form className="yoto-debug-form" onSubmit={(event) => void handleCustomDebugRequest(event)}>
            <h4 className="settings-section-title">Custom Yoto API request</h4>
            <label>
              Method
              <select
                value={customDebugMethod}
                onChange={(event) =>
                  setCustomDebugMethod(event.target.value as "GET" | "POST" | "PUT" | "PATCH" | "DELETE")
                }
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="PATCH">PATCH</option>
                <option value="DELETE">DELETE</option>
              </select>
            </label>
            <label>
              Path
              <input
                onChange={(event) => setCustomDebugPath(event.target.value)}
                placeholder="/card/family/library/groups"
                value={customDebugPath}
              />
            </label>
            <label className="yoto-debug-body">
              JSON body
              <textarea
                onChange={(event) => setCustomDebugBody(event.target.value)}
                placeholder='{"name":"My test group"}'
                rows={8}
                value={customDebugBody}
              />
            </label>
            <div className="button-row">
              <button className="secondary-button" disabled={saving || !yotoCredential?.token_storage_ref} type="submit">
                Send custom request
              </button>
              <button
                className="secondary-button"
                disabled={saving}
                onClick={() => setCustomDebugBody("")}
                type="button"
              >
                Clear body
              </button>
            </div>
          </form>
          {yotoDebugResult ? (
            <div className="yoto-debug-result">
              <p>
                Request: {yotoDebugResult.label} · {yotoDebugResult.method} {yotoDebugResult.path}
                {yotoDebugResult.http_status ? ` (${yotoDebugResult.http_status})` : ""}
                {yotoDebugResult.token_refreshed ? " · token refreshed" : ""}
              </p>
              <p className="auth-url-break">URL: {yotoDebugResult.request_url}</p>
              {yotoDebugResult.response_excerpt ? <pre>{yotoDebugResult.response_excerpt}</pre> : null}
              {yotoDebugResult.response_json ? (
                <div className="json-tree-panel">
                  <p className="muted">Structured response</p>
                  <YotoJsonTree value={yotoDebugResult.response_json} />
                </div>
              ) : null}
              {yotoDebugResult.error_detail && yotoDebugResult.error_detail !== yotoDebugResult.response_excerpt ? (
                <pre>{yotoDebugResult.error_detail}</pre>
              ) : null}
            </div>
          ) : null}
          {yotoDebugHistory.length > 0 ? (
            <div className="json-tree-panel">
              <h4 className="settings-section-title">Recent explorer requests</h4>
              <div className="compact-list">
                {yotoDebugHistory.map((entry, index) => (
                  <button
                    className="secondary-button yoto-history-button"
                    key={`${entry.method}:${entry.path}:${index}`}
                    onClick={() => setYotoDebugResult(entry)}
                    type="button"
                  >
                    {entry.method} {entry.path} {entry.http_status ? `(${entry.http_status})` : ""}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
        <button className="primary-button" disabled={saving} type="submit">
          Save settings
        </button>
      </form>
      {error ? <p className="auth-error">{error}</p> : null}
    </section>
  );
}

function YotoOAuthCallbackPage() {
  const [statusMessage, setStatusMessage] = useState("Completing Yoto browser auth...");
  const [error, setError] = useState<string | null>(null);
  const [credential, setCredential] = useState<YotoCredentialStatus | null>(null);

  useEffect(() => {
    async function finishAuth() {
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      const state = params.get("state");
      const storedValue = window.sessionStorage.getItem(yotoPkceStorageKey);
      if (!code || !state) {
        setError("Yoto did not return both code and state.");
        return;
      }
      if (!storedValue) {
        setError("The PKCE verifier is missing from this browser session.");
        return;
      }
      let stored: { verifier?: string; state?: string };
      try {
        stored = JSON.parse(storedValue) as { verifier?: string; state?: string };
      } catch {
        setError("The stored PKCE verifier could not be read.");
        return;
      }
      if (!stored.verifier || stored.state !== state) {
        setError("The returned Yoto OAuth state does not match this browser session.");
        return;
      }
      const exchangeKey = `${state}:${code}`;
      const exchangeStatus = window.sessionStorage.getItem(yotoPkceExchangeKey);
      if (exchangeStatus === `processing:${exchangeKey}` || exchangeStatus === `complete:${exchangeKey}`) {
        setStatusMessage("Yoto browser auth is already being completed for this callback.");
        return;
      }
      window.sessionStorage.setItem(yotoPkceExchangeKey, `processing:${exchangeKey}`);
      try {
        const result = await completeYotoOAuth({
          code,
          state,
          code_verifier: stored.verifier,
        });
        window.sessionStorage.removeItem(yotoPkceStorageKey);
        window.sessionStorage.setItem(yotoPkceExchangeKey, `complete:${exchangeKey}`);
        window.history.replaceState({}, document.title, "/settings/yoto/callback");
        setCredential(result.credential);
        setStatusMessage("Yoto browser auth completed.");
      } catch (callbackError) {
        window.sessionStorage.removeItem(yotoPkceExchangeKey);
        setError(callbackError instanceof Error ? callbackError.message : "Failed to complete Yoto auth.");
      }
    }

    void finishAuth();
  }, []);

  return (
    <section className="panel">
      <p className="eyebrow">Yoto API</p>
      <h2>Browser auth callback</h2>
      {error ? <p className="auth-error">{error}</p> : <p className="settings-note">{statusMessage}</p>}
      {credential ? (
        <div className="settings-connection-panel">
          <p className="settings-note">Status: {credential.status}</p>
          <p className="settings-note">{credential.error_summary}</p>
          <Link className="secondary-button" to="/settings">
            Back to settings
          </Link>
        </div>
      ) : null}
    </section>
  );
}

function AuthGate({
  session,
  onSessionChange,
}: {
  session: SessionResponse | null;
  onSessionChange: (session: SessionResponse | null) => void;
}) {
  const [authOptions, setAuthOptions] = useState<AuthProvidersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [passwordForm, setPasswordForm] = useState({ username: "", password: "" });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadAuthOptions() {
      if (!cancelled) {
        setLoading(true);
        setError(null);
      }
      try {
        const options = await fetchAuthProviders();
        if (!cancelled) {
          setAuthOptions(options);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load auth options.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadAuthOptions();
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  async function handleQuickSelect(userSlug: string) {
    setSubmitting(true);
    setError(null);
    try {
      const nextSession = await quickSelectUser(userSlug);
      onSessionChange(nextSession);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Sign-in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePasswordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const nextSession = await loginWithPassword(passwordForm.username, passwordForm.password);
      onSessionChange(nextSession);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Sign-in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (session) {
    return (
      <section className="auth-panel">
        <div className="auth-panel-header">
          <div>
            <p className="eyebrow">Signed in</p>
            <h2>{session.user.display_name}</h2>
          </div>
          <button className="ghost-button" onClick={() => onSessionChange(null)} type="button">
            Switch user
          </button>
        </div>
        <p className="auth-status">
          Signed in with <strong>{session.user.auth_method}</strong>. {session.message}
        </p>
      </section>
    );
  }

  if (!loading && error && !authOptions) {
    return <BackendUnavailablePanel error={error} onRetry={() => setReloadToken((current) => current + 1)} />;
  }

  return (
    <section className="auth-panel">
      <p className="eyebrow">Authentication</p>
      <h2>Select a household user</h2>
      <p className="auth-copy">
        Start simple for now: choose Krystin or Dale from the home page. Password auth and OAuth
        remain scaffolded behind the same API shape so they can replace this flow cleanly later.
      </p>

      {loading ? <p className="auth-status">Loading auth options...</p> : null}
      {error ? <p className="auth-error">{error}</p> : null}

      <div className="user-grid">
        {authOptions?.users.map((user) => (
          <button
            key={user.slug}
            className="user-card"
            disabled={!user.can_quick_select || submitting}
            onClick={() => void handleQuickSelect(user.slug)}
            type="button"
          >
            <span className="user-name">{user.display_name}</span>
            <span className="user-meta">@{user.username}</span>
            <span className="user-meta">
              {user.has_password ? "Password configured" : "Quick select only"}
            </span>
          </button>
        ))}
      </div>

      <form className="password-form" onSubmit={(event) => void handlePasswordSubmit(event)}>
        <div className="auth-panel-header">
          <div>
            <p className="eyebrow">Scaffolded</p>
            <h3>Password sign-in</h3>
          </div>
          <span className="status-pill">
            {authOptions?.providers.find((provider) => provider.key === "password")?.configured
              ? "Ready"
              : "Not configured"}
          </span>
        </div>
        <label>
          Username
          <input
            autoComplete="username"
            onChange={(event) =>
              setPasswordForm((current) => ({ ...current, username: event.target.value }))
            }
            value={passwordForm.username}
          />
        </label>
        <label>
          Password
          <input
            autoComplete="current-password"
            onChange={(event) =>
              setPasswordForm((current) => ({ ...current, password: event.target.value }))
            }
            type="password"
            value={passwordForm.password}
          />
        </label>
        <button className="primary-button" disabled={submitting} type="submit">
          Sign in with password
        </button>
      </form>

      <div className="oauth-strip">
        <span className="status-pill status-pill-muted">Future</span>
        <p>OAuth 2.0 provider support is reserved in the backend contract and can be enabled later.</p>
      </div>
    </section>
  );
}

function BuildStamp() {
  const [backendBuild, setBackendBuild] = useState<BuildInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [androidUpdate, setAndroidUpdate] = useState<AndroidUpdateState>({
    kind: "unavailable",
    detail: "OTA web updates are only available in the Android app runtime.",
  });

  async function checkAndroidUpdate() {
    if (!isNativeAndroidRuntime()) {
      setAndroidUpdate({
        kind: "unavailable",
        detail: "OTA web updates are only available in the Android app runtime.",
      });
      return;
    }

    let currentVersion: string | null = null;
    let nativeVersion: string | null = null;
    try {
      const current = await CapacitorUpdater.current();
      currentVersion = current.bundle?.version ?? null;
      nativeVersion = current.native ?? null;
      setAndroidUpdate({
        kind: "checking",
        detail: "Checking the webserver for a newer Android web bundle.",
        currentVersion,
        nativeVersion,
      });

      const manifest = await fetchAndroidUpdateManifest();
      if (nativeVersion && manifest.app_version !== nativeVersion) {
        setAndroidUpdate({
          kind: "blocked",
          detail: `Server bundle ${manifest.version} targets app ${manifest.app_version}, but this APK reports ${nativeVersion}. Rebuild the APK for native/plugin changes.`,
          currentVersion,
          nativeVersion,
          remoteVersion: manifest.version,
        });
        return;
      }
      if (currentVersion === manifest.version) {
        setAndroidUpdate({
          kind: "up_to_date",
          detail: `Already running web bundle ${manifest.version}.`,
          currentVersion,
          nativeVersion,
          remoteVersion: manifest.version,
        });
        return;
      }

      const manifestBaseUrl = resolveAndroidUpdateManifestUrl();
      const bundleUrl = new URL(manifest.bundle_url, manifestBaseUrl).toString();
      setAndroidUpdate({
        kind: "downloading",
        detail: `Downloading web bundle ${manifest.version} from the YotoWebMgr webserver.`,
        currentVersion,
        nativeVersion,
        remoteVersion: manifest.version,
        percent: 0,
      });
      const bundle = await CapacitorUpdater.download({
        url: bundleUrl,
        version: manifest.version,
      });
      setAndroidUpdate({
        kind: "ready",
        detail: `Downloaded web bundle ${manifest.version}. Apply it to reload the app onto the new UI/API client.`,
        currentVersion,
        nativeVersion,
        remoteVersion: manifest.version,
        bundleId: bundle.id,
      });
    } catch (updateError) {
      setAndroidUpdate({
        kind: "error",
        detail: updateError instanceof Error ? updateError.message : "Android OTA update check failed.",
        currentVersion,
        nativeVersion,
      });
    }
  }

  async function applyAndroidUpdate() {
    if (androidUpdate.kind !== "ready") {
      return;
    }
    try {
      await CapacitorUpdater.set({ id: androidUpdate.bundleId });
    } catch (applyError) {
      setAndroidUpdate({
        kind: "error",
        detail: applyError instanceof Error ? applyError.message : "Could not apply the downloaded Android update.",
        currentVersion: androidUpdate.currentVersion,
        nativeVersion: androidUpdate.nativeVersion,
      });
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function loadBuildInfo() {
      try {
        const result = await fetchBackendBuildInfo();
        if (!cancelled) {
          setBackendBuild(result);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load backend build info.");
        }
      }
    }

    void loadBuildInfo();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isNativeAndroidRuntime()) {
      return;
    }

    let active = true;

    async function bootstrapAndroidUpdater() {
      try {
        await CapacitorUpdater.notifyAppReady();
      } catch {
        // Ignore; the app should continue even if OTA bookkeeping is unavailable.
      }
      if (active) {
        await checkAndroidUpdate();
      }
    }

    void bootstrapAndroidUpdater();
    const downloadListener = CapacitorUpdater.addListener("download", (event: { percent?: number }) => {
      setAndroidUpdate((current) =>
        current.kind === "downloading"
          ? {
              ...current,
              percent: typeof event.percent === "number" ? event.percent : current.percent,
              detail: `Downloading web bundle ${current.remoteVersion} (${Math.round(
                typeof event.percent === "number" ? event.percent : current.percent,
              )}%).`,
            }
          : current,
      );
    });

    return () => {
      active = false;
      void downloadListener.then((listener) => listener.remove());
    };
  }, []);

  const backendSha = backendBuild?.build_sha ?? "loading";
  const hashesMatch = backendBuild ? backendBuild.build_sha === frontendBuildSha : false;
  const indicatorClass = backendBuild
    ? hashesMatch
      ? "build-indicator build-indicator-match"
      : "build-indicator build-indicator-mismatch"
    : "build-indicator build-indicator-loading";

  return (
    <footer className="build-stamp">
      <div className="build-stamp-row">
        <span className={indicatorClass} aria-hidden="true" />
        <strong>Build</strong>
        <span className="build-chip">UI {frontendBuildSha}</span>
        <span className="build-chip">API {backendSha}</span>
        <span className={`build-status${hashesMatch ? " build-status-match" : ""}`}>
          {backendBuild ? (hashesMatch ? "matched" : "mismatch") : "checking"}
        </span>
      </div>
      <p className="build-stamp-copy">
        {backendBuild ? `Environment: ${backendBuild.environment}` : "Loading backend build info..."}
        {error ? ` ${error}` : ""}
      </p>
      <div className="build-stamp-update-row">
        <span className="build-chip">
          Android OTA {androidUpdate.kind === "ready" ? "downloaded" : androidUpdate.kind.replace(/_/g, " ")}
        </span>
        {"remoteVersion" in androidUpdate && androidUpdate.remoteVersion ? (
          <span className="build-chip">Remote {androidUpdate.remoteVersion}</span>
        ) : null}
        {"currentVersion" in androidUpdate && androidUpdate.currentVersion ? (
          <span className="build-chip">Current {androidUpdate.currentVersion}</span>
        ) : null}
        {isNativeAndroidRuntime() ? (
          <button className="ghost-button build-stamp-button" onClick={() => void checkAndroidUpdate()} type="button">
            Check app update
          </button>
        ) : null}
        {androidUpdate.kind === "ready" ? (
          <button className="primary-button build-stamp-button" onClick={() => void applyAndroidUpdate()} type="button">
            Apply web update
          </button>
        ) : null}
      </div>
      <p className="build-stamp-copy">{androidUpdate.detail}</p>
    </footer>
  );
}

export default function App() {
  const [session, setSession] = useState<SessionResponse | null>(() => {
    const stored = window.localStorage.getItem(sessionStorageKey);
    return stored ? (JSON.parse(stored) as SessionResponse) : null;
  });

  useEffect(() => {
    if (session) {
      window.localStorage.setItem(sessionStorageKey, JSON.stringify(session));
      return;
    }
    window.localStorage.removeItem(sessionStorageKey);
  }, [session]);

  return (
    <div className="app-shell">
      <header className="hero">
        <p className="eyebrow">YotoWebMgr</p>
        <h1>Household audio management for Yoto MYO cards.</h1>
        <p className="hero-copy">
          Import preserved originals, prepare Yoto-ready media, plan cards, and track playlist
          history from one place.
        </p>
      </header>

      <AuthGate onSessionChange={setSession} session={session} />

      {session ? (
        <nav className="nav-grid" aria-label="Primary">
          {sections.map((section) => {
            const path = section === "Library" ? "/" : `/${section.toLowerCase()}`;
            return (
              <NavLink
                key={section}
                to={path}
                className={({ isActive }) => `nav-card${isActive ? " nav-card-active" : ""}`}
              >
                {section}
              </NavLink>
            );
          })}
        </nav>
      ) : null}

      <main>
        <Routes>
          <Route
            path="/"
            element={session ? <LibraryPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/library/:itemId"
            element={session ? <LibraryDetailPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/import"
            element={
              session ? <ImportPage session={session} /> : <PlaceholderPage title="Home" />
            }
          />
          <Route
            path="/cards"
            element={session ? <CardsPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/cards/:cardId"
            element={session ? <CardDetailPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/jobs"
            element={session ? <JobsPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/tags"
            element={session ? <TagsPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/settings"
            element={session ? <SettingsPage /> : <PlaceholderPage title="Home" />}
          />
          <Route path="/settings/yoto/callback" element={<YotoOAuthCallbackPage />} />
        </Routes>
      </main>
      <BuildStamp />
    </div>
  );
}
