// Same-origin API client. Every call goes to /api/*, which the Vite dev server proxies
// to the local FastAPI backend at http://127.0.0.1:8000. No absolute remote URLs anywhere.

import type {
  AnswerResponse,
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
  TranscriptResponse,
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
  } catch (caught) {
    // A user-initiated cancel must not be reported as a backend failure.
    if (caught instanceof DOMException && caught.name === "AbortError") {
      throw caught;
    }
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

/**
 * The full journey in one call: safety route -> retrieval -> grounded drafting ->
 * independent claim verification. Runs several sequential local model calls and
 * routinely takes 30-120s, so callers MUST pass an AbortSignal and show progress.
 * There is no streaming: this resolves once, at the end.
 */
export type OutputLanguage = "en" | "hi";

export function postAnswer(
  facts: ConfirmedFacts,
  confirmedUrgencies: string[],
  limit: number,
  outputLanguage: OutputLanguage = "en",
  signal?: AbortSignal,
): Promise<AnswerResponse> {
  return postJson<AnswerResponse>(
    "/api/answer",
    {
      facts,
      confirmed_urgencies: confirmedUrgencies,
      approved_profiles: [],
      limit,
      // Only the explanation is translated. The official excerpts stay in the
      // language of the source.
      output_language: outputLanguage,
    },
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

/** One server-sent event from the Devil's Advocate stream. */
export interface AdvocateEvent {
  stage?: "advocate" | "opponent" | "rebuttal";
  kind?: "preparing" | "started" | "token" | "completed" | "error";
  text?: string;
  message?: string;
}

/**
 * Stream the Devil's Advocate stages. EventSource cannot POST a body, so the SSE
 * frames are read from a fetch ReadableStream and parsed by hand. Each `data:`
 * line is one JSON event. The whole exchange stays on the loopback backend.
 */
export async function streamDevilsAdvocate(
  payload: { facts: ConfirmedFacts; approved_profiles?: string[]; limit?: number },
  onEvent: (event: AdvocateEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch("/api/devils-advocate", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(payload),
      credentials: "omit",
      cache: "no-store",
      referrerPolicy: "no-referrer",
      signal,
    });
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === "AbortError") {
      throw caught;
    }
    throw new OfflineBackendError(BACKEND_DOWN_MESSAGE);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  if (!response.body) {
    throw new OfflineBackendError(BACKEND_DOWN_MESSAGE);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    // SSE frames are separated by a blank line.
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      for (const line of frame.split("\n")) {
        if (line.startsWith("data:")) {
          const json = line.slice(5).trim();
          if (json) {
            try {
              onEvent(JSON.parse(json) as AdvocateEvent);
            } catch {
              // A malformed frame is skipped rather than aborting the stream.
            }
          }
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export interface CommunityResponse {
  heading: string;
  what_help_is_needed: string;
  situation: string;
  rights: string[];
  next_steps: string[];
  citations: string[];
  caveats: string[];
  text: string;
}

/** Build a third-person intermediary brief from a published case. */
export function postCommunity(
  payload: { facts: ConfirmedFacts; approved_profiles?: string[]; limit?: number },
  signal?: AbortSignal,
): Promise<CommunityResponse> {
  return postJson<CommunityResponse>("/api/community", payload, signal);
}

/** Fetch a Rights Card PNG for a published case. Returns an object URL to revoke. */
export async function postRightsCard(
  payload: {
    facts: ConfirmedFacts;
    approved_profiles?: string[];
    legal_aid_district?: string | null;
    legal_aid_state?: string | null;
    limit?: number;
  },
  signal?: AbortSignal,
): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch("/api/rights-card", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "image/png" },
      body: JSON.stringify(payload),
      credentials: "omit",
      cache: "no-store",
      referrerPolicy: "no-referrer",
      signal,
    });
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === "AbortError") {
      throw caught;
    }
    throw new OfflineBackendError(BACKEND_DOWN_MESSAGE);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return response.blob();
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

export const PDF_TYPE = "application/pdf";
export const MAX_PDF_BYTES = 15 * 1024 * 1024;

export interface PdfResponse {
  text: string;
  page_count: number;
  pages_with_text: number;
  scanned_pages: number[];
  truncated: boolean;
}

export async function postPdf(file: File, signal?: AbortSignal): Promise<PdfResponse> {
  if (file.size > MAX_PDF_BYTES) {
    throw new ApiError(400, "file_too_large", "The PDF is larger than 15 MB.", "file");
  }
  const form = new FormData();
  form.append("file", file, file.name);
  return request<PdfResponse>("/api/pdf", { method: "POST", body: form, signal });
}

// The backend accepts only WAV/FLAC; the browser's MediaRecorder produces
// WebM/Opus, which it rejects. So mic audio is captured as raw PCM and encoded
// into a 16 kHz mono 16-bit WAV here, entirely in the browser. Nothing is uploaded
// anywhere except the loopback backend.
export const TRANSCRIBE_SAMPLE_RATE = 16_000;

/** Downsample interleaved-mono Float32 PCM to the target rate by averaging windows. */
function downsample(input: Float32Array, inputRate: number, targetRate: number): Float32Array {
  if (targetRate >= inputRate) {
    return input;
  }
  const ratio = inputRate / targetRate;
  const outputLength = Math.floor(input.length / ratio);
  const output = new Float32Array(outputLength);
  for (let i = 0; i < outputLength; i += 1) {
    const start = Math.floor(i * ratio);
    const end = Math.min(Math.floor((i + 1) * ratio), input.length);
    let sum = 0;
    for (let j = start; j < end; j += 1) {
      sum += input[j];
    }
    output[i] = sum / Math.max(1, end - start);
  }
  return output;
}

/** Encode mono Float32 PCM as a 16-bit PCM WAV the backend's validator accepts. */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeString = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i += 1) {
      view.setUint8(offset + i, text.charCodeAt(i));
    }
  };
  const dataBytes = samples.length * 2;
  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true); // PCM fmt chunk size
  view.setUint16(20, 1, true); // audio format = PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate = rate * blockAlign
  view.setUint16(32, 2, true); // block align = channels * bytesPerSample
  view.setUint16(34, 16, true); // bits per sample
  writeString(36, "data");
  view.setUint32(40, dataBytes, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += 2;
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export function pcmToWav(samples: Float32Array, inputRate: number): Blob {
  return encodeWav(downsample(samples, inputRate, TRANSCRIBE_SAMPLE_RATE), TRANSCRIBE_SAMPLE_RATE);
}

export async function postTranscribe(
  wav: Blob,
  language: "auto" | "hi" | "en" = "auto",
  signal?: AbortSignal,
): Promise<TranscriptResponse> {
  const form = new FormData();
  form.append("file", wav, "speech.wav");
  form.append("language", language);
  return request<TranscriptResponse>("/api/transcribe", {
    method: "POST",
    body: form,
    signal,
  });
}
