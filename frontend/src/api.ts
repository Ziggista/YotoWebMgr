export type AuthProviderType = "household_select" | "password" | "oauth2";

export interface AuthProvider {
  key: string;
  type: AuthProviderType;
  label: string;
  enabled: boolean;
  configured: boolean;
  description: string;
}

export interface AuthUserSummary {
  slug: string;
  display_name: string;
  username: string;
  has_password: boolean;
  can_quick_select: boolean;
}

export interface AuthProvidersResponse {
  providers: AuthProvider[];
  users: AuthUserSummary[];
}

export interface SessionUser {
  slug: string;
  display_name: string;
  username: string;
  auth_method: AuthProviderType;
}

export interface SessionResponse {
  user: SessionUser;
  session_mode: "scaffold";
  message: string;
}

export interface AppSettings {
  target_duration_hours: number;
  target_size_mb: number;
  normalise_loudness_default: boolean;
  audiobook_bitrate_kbps: number;
  music_bitrate_kbps: number;
  yoto_api_enabled: boolean;
  yoto_api_base_url: string;
  yoto_auth_base_url: string;
  yoto_client_id: string;
  yoto_redirect_uri: string;
  yoto_oauth_scope: string;
  yoto_upload_timeout_seconds: number;
  yoto_transcode_poll_seconds: number;
  yoto_transcode_timeout_minutes: number;
}

export interface LibraryItem {
  id: number;
  title: string;
  content_type: string;
  status: string;
  cover_art_path: string | null;
  playlist_always_play_from_start: boolean;
  playlist_shuffle_tracks: boolean;
  playlist_hide_track_numbers: boolean;
  readiness_status: string;
  readiness_detail: string | null;
  notes: string | null;
  created_at: string;
  media_url: string | null;
  stream_url: string | null;
}

export interface PlaylistTrack {
  id: number;
  library_item_id: number;
  title: string;
  source_path: string | null;
  source_url: string | null;
  track_number: number;
  duration_seconds: number | null;
  icon_path: string | null;
  track_behavior: string;
  is_stream: boolean;
  stream_url: string | null;
  podcast_episode_guid: string | null;
  created_at: string;
}

export interface PodcastEpisode {
  id: number;
  feed_id: number;
  guid: string | null;
  title: string;
  description: string | null;
  episode_url: string | null;
  published_at: string | null;
  duration_seconds: number | null;
  selected_for_playlist: boolean;
  created_at: string;
}

export interface PodcastFeed {
  id: number;
  library_item_id: number;
  rss_url: string;
  title: string | null;
  description: string | null;
  artwork_url: string | null;
  last_fetched_at: string | null;
  created_at: string;
  episodes: PodcastEpisode[];
}

export interface SplitPoint {
  id: number;
  library_item_id: number;
  timestamp_seconds: number;
  title: string;
  part_number: number | null;
  created_at: string;
}

export interface LibraryItemDetail {
  item: LibraryItem;
  tracks: PlaylistTrack[];
  podcast_feeds: PodcastFeed[];
  split_points: SplitPoint[];
}

export interface ReadinessCheck {
  key: string;
  label: string;
  ok: boolean;
  detail: string;
}

export interface ReadinessResponse {
  library_item_id: number;
  status: string;
  checks: ReadinessCheck[];
}

export interface CardPlanTrack {
  track_id: number;
  title: string;
  track_number: number;
  duration_seconds: number | null;
  estimated_size_mb: number | null;
}

export interface CardPlanPart {
  part_number: number;
  title: string;
  duration_seconds: number;
  estimated_size_mb: number;
  track_count: number;
  tracks: CardPlanTrack[];
  warnings: string[];
}

export interface CardPlan {
  library_item_id: number;
  target_duration_seconds: number;
  target_size_mb: number;
  total_duration_seconds: number;
  estimated_total_size_mb: number;
  parts: CardPlanPart[];
  warnings: string[];
}

export interface ImportRequest {
  id: number;
  title: string;
  source_type: string;
  source_path: string | null;
  content_type: string;
  status: string;
  pending_delete: boolean;
  created_at: string;
  related_library_item_id: number | null;
  related_job_id: number | null;
}

export interface ImportSourceInfo {
  filesystem_drop_path: string;
  browser_upload_path: string;
  allowed_extensions: string[];
}

export interface Job {
  id: number;
  type: string;
  status: string;
  pending_delete: boolean;
  retry_count: number;
  max_retries: number;
  progress_percent: number;
  progress_message: string;
  error_summary: string | null;
  related_library_item_id: number | null;
  related_import_id: number | null;
  related_card_id: number | null;
  created_at: string;
}

export interface PhysicalCard {
  id: number;
  card_code: string;
  programmable_id: string | null;
  display_name: string;
  card_kind: string;
  nfc_technology: string | null;
  chip_type: string | null;
  memory_size_bytes: number | null;
  ndef_prepared: boolean;
  ndef_format_command: string | null;
  programming_app: string | null;
  source_card_code: string | null;
  is_reusable_transfer_card: boolean;
  ready_to_link_in_app: boolean;
  linked_manually: boolean;
  overwrite_ok: boolean;
  downloaded_to_player_confirmed: boolean;
  needs_player_download: boolean;
  current_library_item_id: number | null;
  pending_job_id: number | null;
  yoto_playlist_uri: string | null;
  status: string;
  label_color: string | null;
  tested: boolean;
  last_linked_at: string | null;
  last_programmed_at: string | null;
  last_tested_at: string | null;
  notes: string | null;
  created_at: string;
}

export interface LinkCardResponse {
  library_item: LibraryItem;
  card: PhysicalCard;
  job: Job;
  requires_split_plan: boolean;
  estimated_source_size_mb: number | null;
}

async function errorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? fallback;
  } catch {
    return fallback;
  }
}

export async function fetchAuthProviders(): Promise<AuthProvidersResponse> {
  const response = await fetch("/api/v1/auth/providers");
  if (!response.ok) {
    throw new Error("Failed to load authentication options.");
  }
  return response.json() as Promise<AuthProvidersResponse>;
}

export async function quickSelectUser(userSlug: string): Promise<SessionResponse> {
  const response = await fetch("/api/v1/auth/session/select", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_slug: userSlug }),
  });

  if (!response.ok) {
    throw new Error("Unable to create quick-select session.");
  }
  return response.json() as Promise<SessionResponse>;
}

export async function loginWithPassword(
  username: string,
  password: string,
): Promise<SessionResponse> {
  const response = await fetch("/api/v1/auth/session/password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    throw new Error("Invalid username or password.");
  }
  return response.json() as Promise<SessionResponse>;
}

export async function fetchSettings(): Promise<AppSettings> {
  const response = await fetch("/api/v1/settings");
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to load settings."));
  }
  return response.json() as Promise<AppSettings>;
}

export async function updateSettings(payload: Partial<AppSettings>): Promise<AppSettings> {
  const response = await fetch("/api/v1/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to update settings."));
  }
  return response.json() as Promise<AppSettings>;
}

export async function fetchLibraryItems(): Promise<LibraryItem[]> {
  const response = await fetch("/api/v1/library");
  if (!response.ok) {
    throw new Error("Failed to load library.");
  }
  return response.json() as Promise<LibraryItem[]>;
}

export async function fetchLibraryItemDetail(itemId: number): Promise<LibraryItemDetail> {
  const response = await fetch(`/api/v1/library/${itemId}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to load library item."));
  }
  return response.json() as Promise<LibraryItemDetail>;
}

export async function updateLibraryItemSettings(
  itemId: number,
  payload: Partial<LibraryItem>,
): Promise<LibraryItem> {
  const response = await fetch(`/api/v1/library/${itemId}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to update playlist settings."));
  }
  return response.json() as Promise<LibraryItem>;
}

export async function uploadCoverArt(itemId: number, artworkFile: File): Promise<LibraryItem> {
  const formData = new FormData();
  formData.append("artwork_file", artworkFile);
  const response = await fetch(`/api/v1/library/${itemId}/cover-art`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to upload cover art."));
  }
  return response.json() as Promise<LibraryItem>;
}

export async function createRadioStreamTrack(
  itemId: number,
  payload: { title: string; stream_url: string; icon_path?: string | null },
): Promise<PlaylistTrack> {
  const response = await fetch(`/api/v1/library/${itemId}/radio-streams`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to add radio stream."));
  }
  return response.json() as Promise<PlaylistTrack>;
}

export async function updatePlaylistTrack(
  itemId: number,
  trackId: number,
  payload: {
    title?: string;
    source_url?: string | null;
    track_number?: number;
    duration_seconds?: number | null;
    icon_path?: string | null;
    track_behavior?: string;
    stream_url?: string | null;
  },
): Promise<PlaylistTrack> {
  const response = await fetch(`/api/v1/library/${itemId}/tracks/${trackId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to update track."));
  }
  return response.json() as Promise<PlaylistTrack>;
}

export async function createPodcastFeed(
  itemId: number,
  payload: { rss_url: string; title?: string | null },
): Promise<PodcastFeed> {
  const response = await fetch(`/api/v1/library/${itemId}/podcast-feeds`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to add podcast feed."));
  }
  return response.json() as Promise<PodcastFeed>;
}

export async function createSplitPoint(
  itemId: number,
  payload: { timestamp_seconds: number; title: string; part_number?: number | null },
): Promise<SplitPoint> {
  const response = await fetch(`/api/v1/library/${itemId}/split-points`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to save split point."));
  }
  return response.json() as Promise<SplitPoint>;
}

export async function applyTrackIcon(itemId: number, iconPath: string): Promise<PlaylistTrack[]> {
  const response = await fetch(`/api/v1/library/${itemId}/tracks/apply-icon`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ icon_path: iconPath }),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to apply track icon."));
  }
  return response.json() as Promise<PlaylistTrack[]>;
}

export async function fetchReadiness(itemId: number): Promise<ReadinessResponse> {
  const response = await fetch(`/api/v1/library/${itemId}/readiness`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to check readiness."));
  }
  return response.json() as Promise<ReadinessResponse>;
}

export async function fetchCardPlan(itemId: number): Promise<CardPlan> {
  const response = await fetch(`/api/v1/library/${itemId}/card-plan`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to build card plan."));
  }
  return response.json() as Promise<CardPlan>;
}

export async function fetchImports(): Promise<ImportRequest[]> {
  const response = await fetch("/api/v1/imports");
  if (!response.ok) {
    throw new Error("Failed to load imports.");
  }
  return response.json() as Promise<ImportRequest[]>;
}

export async function fetchImportSources(): Promise<ImportSourceInfo> {
  const response = await fetch("/api/v1/imports/sources");
  if (!response.ok) {
    throw new Error("Failed to load import storage paths.");
  }
  return response.json() as Promise<ImportSourceInfo>;
}

export async function createImport(payload: {
  title: string;
  source_type: "filesystem" | "browser_upload" | "plex";
  source_path?: string | null;
  content_type: string;
  requested_by_user_slug?: string;
}): Promise<ImportRequest> {
  const response = await fetch("/api/v1/imports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to create import."));
  }
  return response.json() as Promise<ImportRequest>;
}

export async function hideImport(importId: number): Promise<ImportRequest> {
  const response = await fetch(`/api/v1/imports/${importId}/hide`, { method: "POST" });
  if (!response.ok) {
    throw new Error("Failed to hide import.");
  }
  return response.json() as Promise<ImportRequest>;
}

export async function uploadImport(payload: {
  title: string;
  content_type: string;
  requested_by_user_slug?: string;
  media_file: File;
}): Promise<ImportRequest> {
  const formData = new FormData();
  formData.append("title", payload.title);
  formData.append("content_type", payload.content_type);
  if (payload.requested_by_user_slug) {
    formData.append("requested_by_user_slug", payload.requested_by_user_slug);
  }
  formData.append("media_file", payload.media_file);

  const response = await fetch("/api/v1/imports/uploads", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to upload import."));
  }
  return response.json() as Promise<ImportRequest>;
}

export async function fetchJobs(): Promise<Job[]> {
  const response = await fetch("/api/v1/jobs");
  if (!response.ok) {
    throw new Error("Failed to load jobs.");
  }
  return response.json() as Promise<Job[]>;
}

export async function retryJob(jobId: number): Promise<Job> {
  const response = await fetch(`/api/v1/jobs/${jobId}/retry`, { method: "POST" });
  if (!response.ok) {
    throw new Error("Failed to retry job.");
  }
  return response.json() as Promise<Job>;
}

export async function fetchCards(): Promise<PhysicalCard[]> {
  const response = await fetch("/api/v1/cards");
  if (!response.ok) {
    throw new Error("Failed to load cards.");
  }
  return response.json() as Promise<PhysicalCard[]>;
}

export async function createCard(payload: {
  card_code: string;
  programmable_id?: string | null;
  display_name: string;
  card_kind: string;
  nfc_technology?: string | null;
  chip_type?: string | null;
  memory_size_bytes?: number | null;
  ndef_prepared: boolean;
  ndef_format_command?: string | null;
  programming_app?: string | null;
  source_card_code?: string | null;
  is_reusable_transfer_card: boolean;
  ready_to_link_in_app?: boolean;
  linked_manually?: boolean;
  overwrite_ok?: boolean;
  downloaded_to_player_confirmed?: boolean;
  needs_player_download?: boolean;
  yoto_playlist_uri?: string | null;
  status: string;
  label_color?: string | null;
  tested: boolean;
  last_linked_at?: string | null;
  notes?: string | null;
}): Promise<PhysicalCard> {
  const response = await fetch("/api/v1/cards", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(response.status === 409 ? "That card ID already exists." : "Failed to create card.");
  }
  return response.json() as Promise<PhysicalCard>;
}

export async function linkLibraryItemToCard(
  libraryItemId: number,
  cardId: number,
): Promise<LinkCardResponse> {
  const response = await fetch(`/api/v1/library/${libraryItemId}/link-card`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ card_id: cardId }),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to link library item to card."));
  }
  return response.json() as Promise<LinkCardResponse>;
}
