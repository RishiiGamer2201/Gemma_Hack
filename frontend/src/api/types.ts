// Types mirroring the local FastAPI contract (http://127.0.0.1:8000, proxied at /api).
// Verified against the backend's live /openapi.json. Response models carry extra fields
// that the UI ignores; request models use `additionalProperties: false`, so request
// payloads must contain exactly the permitted keys.

export interface HealthResponse {
  corpus_loaded: boolean;
  chunk_count: number;
  corpus_sha256: string | null;
  corpus_error: string | null;
  ollama_reachable: boolean;
  model: string;
}

export interface LanguageInfo {
  language: string;
  devanagari_letters: number;
  latin_letters: number;
  romanized_hindi_markers: number;
  method?: string;
}

/** Closed enum on the backend (UrgencyCategory). */
export type UrgencyCategory =
  | "arrest_or_detention"
  | "violence"
  | "immediate_eviction"
  | "expiring_deadline"
  | "child_safety"
  | "self_harm"
  | "medical_emergency";

export interface UrgencySignal {
  category: UrgencyCategory;
  matched_phrase: string;
}

/**
 * The shape returned by /api/intake (IntakeFacts) and the UI's editing model.
 * Note: `documents` exists here but NOT on ConfirmedFacts.
 */
export interface Facts {
  incident_summary: string;
  incident_date: string | null;
  jurisdiction: string | null;
  location: string | null;
  domain: string;
  parties: string[];
  material_facts: string[];
  documents: string[];
  missing_material_facts: string[];
}

/**
 * The shape accepted by /api/route and /api/evidence (ConfirmedFacts).
 * `additionalProperties: false` — sending `documents` here is a 422.
 */
export interface ConfirmedFacts {
  incident_summary: string;
  incident_date: string | null;
  jurisdiction: string | null;
  location: string | null;
  domain: string;
  parties: string[];
  material_facts: string[];
  missing_material_facts: string[];
  input_language: string;
  confirmed: boolean;
  confirmed_at: string | null;
}

export interface IntakeResponse {
  normalized_text: string;
  language: LanguageInfo;
  urgency_signals: UrgencySignal[];
  restatement: string;
  facts: Facts;
  requires_confirmation?: boolean;
  confirmed?: boolean;
}

export type RoutePriority =
  | "immediate_human_help"
  | "hard_abstain"
  | "needs_information"
  | "standard";

export interface MissingQuestion {
  fact_key: string;
  question: string;
  reason: string;
}

/** DocumentSafetyWarning — a prompt-injection pattern found in untrusted document text. */
export interface DocumentSafetyWarning {
  warning_code: string;
  pattern_name: string;
  instruction_ignored: boolean;
}

/** RoleSignal — a detected power relationship between the parties. */
export interface RoleSignal {
  relationship: string;
  matched_role_terms: string[];
  label: string;
}

/** SafetyRouteDecision. */
export interface RouteResponse {
  facts_fingerprint?: string;
  priority: RoutePriority;
  domain: string | null;
  jurisdiction?: string | null;
  incident_date?: string | null;
  confirmed_urgencies?: UrgencyCategory[];
  role_signals: RoleSignal[];
  protective_prompts: string[];
  missing_questions: MissingQuestion[];
  document_warnings: DocumentSafetyWarning[];
  general_explanation_allowed: boolean;
  human_help_required: boolean;
  terminal_reason: string | null;
}

/** Human-readable text for a DocumentSafetyWarning. */
export function describeDocumentWarning(warning: DocumentSafetyWarning): string {
  const pattern = warning.pattern_name.replace(/_/g, " ");
  return `An uploaded document contained text that looks like an instruction to this system ("${pattern}"). It was ignored and had no effect on the result.`;
}

/** Human-readable text for a RoleSignal. */
export function describeRoleSignal(signal: RoleSignal): string {
  const relationship = signal.relationship.replace(/_/g, " ");
  return `${relationship} (${signal.matched_role_terms.join(", ")})`;
}

/** SourceEvidence. `section` and `heading` are nullable. */
export interface EvidenceItem {
  source_id: string;
  jurisdiction?: string | null;
  act: string;
  section: string | null;
  heading: string | null;
  language?: string | null;
  excerpt: string;
  excerpt_truncated?: boolean;
  effective_from: string | null;
  effective_to: string | null;
  status: string | null;
  priority: number | string | null;
  official_url: string | null;
  page: number | string | null;
  retrieved_at: string | null;
  sha256: string | null;
  ocr_used?: boolean;
}

export interface EvidenceResponse {
  query: string;
  evidence: EvidenceItem[];
  warnings: string[];
  undated_source_ids?: string[];
  trace?: unknown;
}

export interface LegalAidContact {
  contact_id: string;
  authority: string;
  state: string;
  district?: string | null;
  officer_name?: string | null;
  designation: string;
  address?: string | null;
  phone: string;
  email: string;
  official_url: string;
  verified_date: string;
  source_sha256?: string;
  needs_address_review?: boolean;
}

export interface LegalAidFallback {
  fallback_id: string;
  service: string;
  scope?: string;
  phone: string;
  official_url: string;
  verified_date?: string;
  description: string;
}

/** LegalAidSearchResult. */
export interface LegalAidResponse {
  match_status: string;
  normalized_query?: unknown;
  contacts: LegalAidContact[];
  fallbacks: LegalAidFallback[];
  warnings: string[];
  source_freshness?: unknown;
}

export interface ChecklistItem {
  item_id: string;
  label: string;
  sensitive: boolean;
}

export interface ChecklistTemplate {
  template_id: string;
  title: string;
  scenario?: string;
  domain?: string;
  guidance_label: string;
  items: ChecklistItem[];
}

export interface ChecklistSummary {
  template_id: string;
  title?: string;
  scenario?: string;
  domain?: string;
}

/** GET /api/checklists returns {templates: [...]}; a bare list is tolerated too. */
export type ChecklistIndexResponse =
  | Array<ChecklistSummary | string>
  | { templates: Array<ChecklistSummary | string> }
  | { checklists: Array<ChecklistSummary | string> };

/** OCRResult. `mean_confidence_percent` is nullable. */
export interface OcrResponse {
  text: string;
  mean_confidence_percent: number | null;
  width: number;
  height: number;
  image_format?: string;
  language?: string;
  processing_seconds?: number;
}

/** TranscriptResponse from POST /api/transcribe. The transcript is a DRAFT. */
export interface TranscriptResponse {
  transcript: string;
  detected_language: string | null;
  language_probability: number | null;
  backend?: string;
  processing_seconds?: number;
}

/** ClaimVerdict — the independent verifier's finding for one claim. */
export type ClaimVerdict = "supported" | "contradicted" | "insufficient";

/** ClaimView — a drafted claim plus the verifier's verdict. Top-level `claims`. */
export interface ClaimView {
  claim_id: string;
  text: string;
  cited_source_ids: string[];
  verdict: ClaimVerdict;
  verdict_reason: string;
  evidence_source_ids: string[];
}

/** LegalClaim — the raw claim inside StructuredLegalAnswer (no verdict). */
export interface LegalClaim {
  claim_id: string;
  text: string;
  cited_source_ids: string[];
}

/**
 * StructuredLegalAnswer. Every list may legitimately be empty: an empty
 * `deadlines` means the sources state no deadline. Never fill an empty list.
 */
export interface StructuredLegalAnswer {
  situation: string;
  applicable_law: string[];
  rights: string[];
  options: string[];
  evidence_to_preserve: string[];
  deadlines: string[];
  consequences_of_inaction: string[];
  next_steps: string[];
  limitations: string[];
  claims: LegalClaim[];
}

/**
 * AnswerResponse from POST /api/answer — the full journey
 * (safety route -> retrieval -> grounded drafting -> claim verification).
 */
export interface AnswerResponse {
  stage: string;
  /** THE ONLY field that authorises showing legal content. */
  published: boolean;
  route: RouteResponse;
  answer: StructuredLegalAnswer | null;
  claims: ClaimView[];
  evidence: EvidenceItem[];
  warnings: string[];
  query: string | null;
}

/** ErrorResponse: {code, message, field?}. */
export interface ApiErrorBody {
  code?: string;
  message?: string;
  field?: string;
  detail?: unknown;
}

// LegalDomain is a closed enum. Sending anything else returns a 422
// validation_error on body.facts.domain.
export const DOMAIN_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "criminal", label: "Criminal / police" },
  { value: "labour", label: "Labour / employment" },
  { value: "consumer", label: "Consumer" },
  { value: "tenancy_property", label: "Tenancy / property" },
  { value: "constitutional", label: "Constitutional / fundamental rights" },
  { value: "other", label: "Other / unclear" },
];

export const DEFAULT_DOMAIN = "other";

/**
 * Convert the editable UI facts into the exact ConfirmedFacts payload the backend
 * accepts. `documents` is dropped (route/evidence forbid it), and the confirmation
 * flags are stamped here — this conversion is the hard gate made concrete.
 */
export function toConfirmedFacts(
  facts: Facts,
  inputLanguage: string,
  confirmedAt: string,
): ConfirmedFacts {
  return {
    incident_summary: facts.incident_summary,
    incident_date: facts.incident_date || null,
    jurisdiction: facts.jurisdiction || null,
    location: facts.location || null,
    domain: facts.domain || DEFAULT_DOMAIN,
    parties: facts.parties,
    material_facts: facts.material_facts,
    missing_material_facts: facts.missing_material_facts,
    input_language: inputLanguage || "en",
    confirmed: true,
    confirmed_at: confirmedAt,
  };
}
