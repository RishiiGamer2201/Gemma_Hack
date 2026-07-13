import { useCallback, useEffect, useRef, useState } from "react";

import {
  getHealth,
  postEvidence,
  postIntake,
  postRoute,
} from "./api/client";
import type {
  ConfirmedFacts,
  EvidenceResponse,
  Facts,
  HealthResponse,
  IntakeResponse,
  RouteResponse,
} from "./api/types";
import { DEFAULT_DOMAIN, DOMAIN_OPTIONS, toConfirmedFacts } from "./api/types";
import { ConfirmationGate } from "./components/ConfirmationGate";
import { EvidencePanel } from "./components/EvidencePanel";
import { HealthStatus } from "./components/HealthStatus";
import { IntakePanel } from "./components/IntakePanel";
import { LandingPanel } from "./components/LandingPanel";
import {
  AbstainPanel,
  NeedsInformationPanel,
  RouteContext,
  UrgentSafetyPanel,
} from "./components/RoutingPanels";
import { SidePanel } from "./components/SidePanel";
import { Steps, type StepId } from "./components/Steps";

const EVIDENCE_LIMIT = 8;

/**
 * Maps a backend `missing_questions[].fact_key` onto the Facts field it fills.
 * The backend asks for "legal_domain" but the field is called "domain".
 * Anything not listed here is appended to material_facts as free text instead,
 * so an unknown key can never corrupt a typed field.
 */
const FACT_KEY_TO_FIELD: Record<string, keyof Facts> = {
  incident_date: "incident_date",
  jurisdiction: "jurisdiction",
  location: "location",
  domain: "domain",
  legal_domain: "domain",
  incident_summary: "incident_summary",
};

/** The backend rejects any domain outside its enum with a 422, so clamp it here. */
function clampDomain(domain: string | null | undefined): string {
  if (domain && DOMAIN_OPTIONS.some((option) => option.value === domain)) {
    return domain;
  }
  return DEFAULT_DOMAIN;
}

function emptyFacts(): Facts {
  return {
    incident_summary: "",
    incident_date: null,
    jurisdiction: null,
    location: null,
    domain: DEFAULT_DOMAIN,
    parties: [],
    material_facts: [],
    documents: [],
    missing_material_facts: [],
  };
}

/** Defensive normalisation: the backend is under concurrent development. */
function normalizeFacts(raw: Partial<Facts> | undefined): Facts {
  const base = emptyFacts();
  if (!raw) {
    return base;
  }
  return {
    incident_summary: raw.incident_summary ?? "",
    incident_date: raw.incident_date ?? null,
    jurisdiction: raw.jurisdiction ?? null,
    location: raw.location ?? null,
    domain: clampDomain(raw.domain),
    parties: Array.isArray(raw.parties) ? raw.parties : [],
    material_facts: Array.isArray(raw.material_facts) ? raw.material_facts : [],
    documents: Array.isArray(raw.documents) ? raw.documents : [],
    missing_material_facts: Array.isArray(raw.missing_material_facts)
      ? raw.missing_material_facts
      : [],
  };
}

export function App() {
  const [step, setStep] = useState<StepId>("landing");

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState<unknown>(null);

  const [text, setText] = useState("");
  const [intake, setIntake] = useState<IntakeResponse | null>(null);
  const [intakeBusy, setIntakeBusy] = useState(false);
  const [intakeError, setIntakeError] = useState<unknown>(null);

  const [facts, setFacts] = useState<Facts>(emptyFacts);
  const [confirmedUrgencies, setConfirmedUrgencies] = useState<string[]>([]);
  /** Stamped the moment the user clicks "Yes, this is correct". */
  const [confirmedAt, setConfirmedAt] = useState<string | null>(null);

  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [routeBusy, setRouteBusy] = useState(false);
  const [routeError, setRouteError] = useState<unknown>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [evidenceBusy, setEvidenceBusy] = useState(false);
  const [evidenceError, setEvidenceError] = useState<unknown>(null);

  const mainRef = useRef<HTMLDivElement>(null);

  const refreshHealth = useCallback(async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      setHealth(await getHealth());
    } catch (error) {
      setHealthError(error);
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
  }, [refreshHealth]);

  // Move focus to the top of the new step for keyboard and screen-reader users.
  useEffect(() => {
    mainRef.current?.focus();
  }, [step]);

  const fetchEvidence = useCallback(async (payload: ConfirmedFacts) => {
    setEvidenceBusy(true);
    setEvidenceError(null);
    try {
      setEvidence(await postEvidence(payload, [], EVIDENCE_LIMIT));
    } catch (error) {
      setEvidenceError(error);
      setEvidence(null);
    } finally {
      setEvidenceBusy(false);
    }
  }, []);

  /**
   * The single path from confirmed facts to any legal content. `stamp` is the
   * confirmation time; it is only ever set by the user's explicit confirmation.
   */
  const runRoute = useCallback(
    async (currentFacts: Facts, urgencies: string[], stamp: string) => {
      const payload = toConfirmedFacts(
        currentFacts,
        intake?.language.language ?? "en",
        stamp,
      );
      setRouteBusy(true);
      setRouteError(null);
      try {
        const result = await postRoute(payload, urgencies);
        setRoute(result);
        setStep("result");
        if (result.priority === "standard") {
          await fetchEvidence(payload);
        } else {
          setEvidence(null);
        }
      } catch (error) {
        setRouteError(error);
      } finally {
        setRouteBusy(false);
      }
    },
    [fetchEvidence, intake],
  );

  /** Called by the confirmation gate. Stamps the confirmation time, then routes. */
  function handleConfirm() {
    const stamp = new Date().toISOString();
    setConfirmedAt(stamp);
    void runRoute(facts, confirmedUrgencies, stamp);
  }

  function retryEvidence() {
    fetchEvidence(
      toConfirmedFacts(
        facts,
        intake?.language.language ?? "en",
        confirmedAt ?? new Date().toISOString(),
      ),
    ).catch(() => undefined);
  }

  async function handleIntake() {
    setIntakeBusy(true);
    setIntakeError(null);
    try {
      const result = await postIntake(text);
      setIntake(result);
      setFacts(normalizeFacts(result.facts));
      setConfirmedUrgencies([]); // urgency is never auto-applied
      setConfirmedAt(null); // re-confirmation is required after any re-intake
      setRoute(null);
      setEvidence(null);
      setAnswers({});
      setStep("confirm");
    } catch (error) {
      setIntakeError(error);
    } finally {
      setIntakeBusy(false);
    }
  }

  function handleAnswersSubmit() {
    if (!route) {
      return;
    }
    let next: Facts = { ...facts };
    const extraFacts: string[] = [];

    for (const question of route.missing_questions) {
      const answer = (answers[question.fact_key] ?? "").trim();
      if (!answer) {
        continue;
      }
      const field = FACT_KEY_TO_FIELD[question.fact_key];
      if (field === "domain") {
        // Domain is a closed enum; the UI supplies it from a <select>, but clamp
        // anyway so a stray value can never trigger a 422.
        next = { ...next, domain: clampDomain(answer) };
      } else if (field) {
        next = { ...next, [field]: answer } as Facts;
      } else {
        extraFacts.push(`${question.question} ${answer}`);
      }
    }

    if (extraFacts.length > 0) {
      next = { ...next, material_facts: [...next.material_facts, ...extraFacts] };
    }
    next = {
      ...next,
      missing_material_facts: next.missing_material_facts.filter(
        (key) => !(answers[key] ?? "").trim(),
      ),
    };

    setFacts(next);
    setAnswers({});
    void runRoute(next, confirmedUrgencies, confirmedAt ?? new Date().toISOString());
  }

  function clearSession() {
    setText("");
    setIntake(null);
    setFacts(emptyFacts());
    setConfirmedUrgencies([]);
    setConfirmedAt(null);
    setRoute(null);
    setRouteError(null);
    setIntakeError(null);
    setEvidence(null);
    setEvidenceError(null);
    setAnswers({});
    setStep("landing");
  }

  const urgent = route?.priority === "immediate_human_help";

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <header className="app-header">
        <div>
          <h1>Nyaya Navigator</h1>
          <p className="tagline">
            Offline legal navigation for India — everything runs on this computer
          </p>
        </div>
        <div className="header-actions">
          <HealthStatus
            compact
            health={health}
            loading={healthLoading}
            error={healthError}
            onRefresh={() => void refreshHealth()}
          />
          <button
            type="button"
            className="btn-ghost"
            onClick={clearSession}
            title="Erase the description, facts, and results held in this page"
          >
            Clear session
          </button>
        </div>
      </header>

      {/* Persistent, visible, non-obstructive. Never dismissible. */}
      <p className="disclaimer-bar" role="note">
        <span aria-hidden="true">⚖</span>
        This tool gives legal <strong>information</strong>, not legal advice. It
        cannot predict outcomes. For advice on your case, speak to a lawyer or
        your District Legal Services Authority.
      </p>

      <main className="app-main" id="main-content" ref={mainRef} tabIndex={-1}>
        <div>
          <Steps current={step} />

          {/* Urgent safety content is rendered above everything else. */}
          {urgent && route ? (
            <UrgentSafetyPanel
              route={route}
              facts={facts}
              onRestart={clearSession}
            />
          ) : null}

          {step === "landing" ? (
            <div className="stack">
              <LandingPanel onStart={() => setStep("intake")} />
              <HealthStatus
                health={health}
                loading={healthLoading}
                error={healthError}
                onRefresh={() => void refreshHealth()}
              />
            </div>
          ) : null}

          {step === "intake" ? (
            <IntakePanel
              text={text}
              onTextChange={setText}
              onSubmit={() => void handleIntake()}
              submitting={intakeBusy}
              submitError={intakeError}
              onBack={() => setStep("landing")}
            />
          ) : null}

          {step === "confirm" && intake ? (
            <ConfirmationGate
              intake={intake}
              facts={facts}
              onFactsChange={setFacts}
              confirmedUrgencies={confirmedUrgencies}
              onUrgenciesChange={setConfirmedUrgencies}
              onConfirm={handleConfirm}
              onEditText={() => setStep("intake")}
              submitting={routeBusy}
              error={routeError}
            />
          ) : null}

          {step === "result" && route ? (
            <>
              {route.priority === "hard_abstain" ? (
                <AbstainPanel
                  route={route}
                  onRestart={clearSession}
                  onEditFacts={() => setStep("confirm")}
                />
              ) : null}

              {route.priority === "needs_information" ? (
                <NeedsInformationPanel
                  questions={route.missing_questions}
                  answers={answers}
                  onAnswersChange={setAnswers}
                  onSubmit={handleAnswersSubmit}
                  onEditFacts={() => setStep("confirm")}
                  submitting={routeBusy}
                  error={routeError}
                />
              ) : null}

              {route.priority === "standard" ? (
                <div className="stack">
                  <RouteContext route={route} />
                  <EvidencePanel
                    facts={facts}
                    evidence={evidence}
                    loading={evidenceBusy}
                    error={evidenceError}
                    onRetry={retryEvidence}
                    onEditFacts={() => setStep("confirm")}
                    onRestart={clearSession}
                  />
                </div>
              ) : null}
            </>
          ) : null}

          {step === "result" && !route ? (
            <section className="card">
              <h2>Nothing to show yet</h2>
              <p>The routing result was lost. Please start again.</p>
              <button type="button" className="btn-primary" onClick={clearSession}>
                Start over
              </button>
            </section>
          ) : null}
        </div>

        <SidePanel facts={step === "landing" ? null : facts} />
      </main>

      <footer className="app-footer">
        Runs entirely on 127.0.0.1. No internet requests, no analytics, no
        telemetry, no remote fonts. Uploaded images are not stored by default.
        Official law and effective dates outrank anything the model remembers.
      </footer>
    </div>
  );
}
