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
}

export interface LibraryItem {
  id: number;
  title: string;
  content_type: string;
  status: string;
  notes: string | null;
  created_at: string;
  media_url: string | null;
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
  created_at: string;
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
    throw new Error("Failed to load settings.");
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
    throw new Error("Failed to update settings.");
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
    throw new Error("Failed to create import.");
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
    throw new Error("Failed to upload import.");
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
