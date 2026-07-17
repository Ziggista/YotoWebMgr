const API_BASE_URL_KEY = "yotowebmgr.apiBaseUrl";
const ANDROID_DEFAULT_API_BASE_URL = "http://ziggi-pc-1.tailaf3d4b.ts.net:5175";

export function normalizeApiBaseUrl(value: string) {
  return value.trim().replace(/\/+$/, "");
}

function getDefaultApiBaseUrl() {
  if (typeof window === "undefined") {
    return "";
  }

  const location = window.location;
  if (!location) {
    return "";
  }

  const { hostname, port, protocol, origin } = location;

  if (hostname === "ziggi-pc-1.tailaf3d4b.ts.net" || hostname === "100.65.175.83") {
    return normalizeApiBaseUrl(origin);
  }

  if ((hostname === "localhost" || hostname === "127.0.0.1") && (port === "5175" || port === "5173")) {
    return "";
  }

  if ((protocol === "http:" || protocol === "https:" || protocol === "capacitor:") && hostname === "localhost") {
    return ANDROID_DEFAULT_API_BASE_URL;
  }

  return "";
}

export function getStoredApiBaseUrl() {
  if (typeof window === "undefined") {
    return "";
  }

  const storedApiBaseUrl = window.localStorage.getItem(API_BASE_URL_KEY);
  if (storedApiBaseUrl) {
    return normalizeApiBaseUrl(storedApiBaseUrl);
  }

  return getDefaultApiBaseUrl();
}

export function setStoredApiBaseUrl(value: string) {
  const normalized = normalizeApiBaseUrl(value);

  if (typeof window !== "undefined") {
    if (normalized) {
      window.localStorage.setItem(API_BASE_URL_KEY, normalized);
    } else {
      window.localStorage.removeItem(API_BASE_URL_KEY);
    }
  }

  return normalized;
}

export function clearStoredApiBaseUrl() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(API_BASE_URL_KEY);
  }
}

export function hasStoredApiBaseUrl() {
  return getStoredApiBaseUrl().length > 0;
}

export function resolveApiUrl(path: string) {
  const apiBaseUrl = getStoredApiBaseUrl();
  return apiBaseUrl ? `${apiBaseUrl}${path}` : path;
}
