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
