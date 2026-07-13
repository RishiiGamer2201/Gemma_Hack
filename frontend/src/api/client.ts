// Same-origin API client. Every call goes to /api/*, which the Vite dev server proxies
// to the local FastAPI backend at http://127.0.0.1:8000. No absolute remote URLs anywhere.

import type {
  ApiErrorBody,
  ChecklistIndexResponse,
  ChecklistSummary,
  ChecklistTemplate,
  ConfirmedFacts,
  EvidenceResponse,
  HealthResponse,
  IntakeResponse,
  LegalAidResponse,
  OcrResponse,
  RouteResponse,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly field?: string;

  constructor(status: number, code: string, message: string, field?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

/** Network/proxy failure — usually "the backend is not running". */
export class OfflineBackendError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OfflineBackendError";
  }
}

const BACKEND_DOWN_MESSAGE =
  "The local backend at 127.0.0.1:8000 is not responding. Start the API server, then retry. Nothing was sent over the internet.";

export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    const field = error.field ? ` (field: ${error.field})` : "";
    return `${error.message}${field}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error.";
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody | null = null;
  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    // Non-JSON body: an empty response, or the Vite proxy's ECONNREFUSED 500 page.
  }

  if (!body || (!body.message && !body.detail && !body.code)) {
    // A 5xx with no structured body almost always means the backend process is down,
    // because the dev proxy answers with 500 when it cannot reach 127.0.0.1:8000.
    if (response.status >= 500) {
      return new ApiError(response.status, "backend_unreachable", BACKEND_DOWN_MESSAGE);
    }
    return new ApiError(
      response.status,
      `http_${response.status}`,
      `The local backend returned HTTP ${response.status}.`,
    );
  }

  const detail = typeof body.detail === "string" ? body.detail : undefined;
  const message =
    body.message ?? detail ?? `The local backend returned HTTP ${response.status}.`;
  return new ApiError(
    response.status,
    body.code ?? `http_${response.status}`,
    message,
    body.field,
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      // Never send credentials or cookies anywhere.
      credentials: "omit",
      cache: "no-store",
      referrerPolicy: "no-referrer",
    });
  } catch {
    throw new OfflineBackendError(BACKEND_DOWN_MESSAGE);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function postJson<T>(path: string, payload: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health", { method: "GET", signal });
}

export function postIntake(text: string, signal?: AbortSignal): Promise<IntakeResponse> {
  return postJson<IntakeResponse>("/api/intake", { text }, signal);
}

// RouteRequest and EvidenceRequest both use `additionalProperties: false` and expect
// ConfirmedFacts (which has no `documents` key). Build the payload with toConfirmedFacts.
export function postRoute(
  facts: ConfirmedFacts,
  confirmedUrgencies: string[],
  requestedOutput?: string,
  signal?: AbortSignal,
): Promise<RouteResponse> {
  return postJson<RouteResponse>(
    "/api/route",
    {
      facts,
      confirmed_urgencies: confirmedUrgencies,
      ...(requestedOutput ? { requested_output: requestedOutput } : {}),
    },
    signal,
  );
}

export function postEvidence(
  facts: ConfirmedFacts,
  approvedProfiles: string[],
  limit: number,
  signal?: AbortSignal,
): Promise<EvidenceResponse> {
  return postJson<EvidenceResponse>(
    "/api/evidence",
    { facts, approved_profiles: approvedProfiles, limit },
    signal,
  );
}

export function postLegalAid(
  districtOrCity: string,
  state?: string,
  signal?: AbortSignal,
): Promise<LegalAidResponse> {
  return postJson<LegalAidResponse>(
    "/api/legal-aid",
    {
      district_or_city: districtOrCity,
      ...(state ? { state } : {}),
    },
    signal,
  );
}

function normalizeChecklistIndex(raw: ChecklistIndexResponse): ChecklistSummary[] {
  const list: Array<ChecklistSummary | string> = Array.isArray(raw)
    ? raw
    : "templates" in raw
      ? raw.templates
      : "checklists" in raw
        ? raw.checklists
        : [];
  return list.map((entry) =>
    typeof entry === "string" ? { template_id: entry } : entry,
  );
}

export async function getChecklists(signal?: AbortSignal): Promise<ChecklistSummary[]> {
  const raw = await request<ChecklistIndexResponse>("/api/checklists", {
    method: "GET",
    signal,
  });
  return normalizeChecklistIndex(raw);
}

export function getChecklist(
  templateId: string,
  signal?: AbortSignal,
): Promise<ChecklistTemplate> {
  return request<ChecklistTemplate>(
    `/api/checklists/${encodeURIComponent(templateId)}`,
    { method: "GET", signal },
  );
}

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const ALLOWED_UPLOAD_TYPES = ["image/png", "image/jpeg"];

export async function postOcr(file: File, signal?: AbortSignal): Promise<OcrResponse> {
  // Client-side validation mirrors the backend's rules so the user gets a fast,
  // clear message. The backend remains the authority.
  if (!ALLOWED_UPLOAD_TYPES.includes(file.type)) {
    throw new ApiError(
      400,
      "unsupported_file_type",
      "Only PNG and JPEG images can be read. Convert the file, or type the text instead.",
      "file",
    );
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new ApiError(
      400,
      "file_too_large",
      "The image is larger than 10 MB. Use a smaller photo.",
      "file",
    );
  }
  const form = new FormData();
  form.append("file", file, file.name);
  return request<OcrResponse>("/api/ocr", {
    method: "POST",
    body: form,
    signal,
  });
}
