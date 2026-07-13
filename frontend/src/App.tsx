import { useCallback, useEffect, useRef, useState } from "react";

import { getHealth, postAnswer, postIntake } from "./api/client";
import type {
  AnswerResponse,
  Facts,
  HealthResponse,
  IntakeResponse,
} from "./api/types";
import { DEFAULT_DOMAIN, DOMAIN_OPTIONS, toConfirmedFacts } from "./api/types";
import { AnswerProgress } from "./components/AnswerProgress";
import { AnswerView } from "./components/AnswerView";
import { ConfirmationGate } from "./components/ConfirmationGate";
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
import { WithheldNotice } from "./components/WithheldNotice";

/** AnswerRequest.limit accepts 1-8 and defaults to 6. */
const EVIDENCE_LIMIT = 6;

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

  /** The single /api/answer result: safety route, answer, claims, evidence, warnings. */
  const [result, setResult] = useState<AnswerResponse | null>(null);
  const [answerBusy, setAnswerBusy] = useState(false);
  const [answerError, setAnswerError] = useState<unknown>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const mainRef = useRef<HTMLDivElement>(null);
  /** Lets the user cancel the long (30-120s) answer run. */
  const abortRef = useRef<AbortController | null>(null);

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

  /**
   * The one path from confirmed facts to any legal content. /api/answer runs the whole
   * journey (safety route -> retrieval -> drafting -> claim verification) in a single
   * call, so there is no separate /api/route or /api/evidence step any more.
   */
  const runAnswer = useCallback(
    async (currentFacts: Facts, urgencies: string[], stamp: string) => {
      const payload = toConfirmedFacts(
        currentFacts,
        intake?.language.language ?? "en",
        stamp,
      );
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setAnswerBusy(true);
      setAnswerError(null);
      try {
        const response = await postAnswer(
          payload,
          urgencies,
          EVIDENCE_LIMIT,
          controller.signal,
        );
        setResult(response);
        setStep("result");
      } catch (error) {
        // A cancel is a user action, not an error to shout about.
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setAnswerError(error);
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
        setAnswerBusy(false);
      }
    },
    [intake],
  );

  function cancelAnswer() {
    abortRef.current?.abort();
    abortRef.current = null;
    setAnswerBusy(false);
  }

  /** Called by the confirmation gate. Stamps the confirmation time, then runs. */
  function handleConfirm() {
    const stamp = new Date().toISOString();
    setConfirmedAt(stamp);
    void runAnswer(facts, confirmedUrgencies, stamp);
  }

  function retryAnswer() {
    void runAnswer(
      facts,
      confirmedUrgencies,
      confirmedAt ?? new Date().toISOString(),
    );
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
      setResult(null);
      setAnswerError(null);
      setAnswers({});
      setStep("confirm");
    } catch (error) {
      setIntakeError(error);
    } finally {
      setIntakeBusy(false);
    }
  }

  function handleAnswersSubmit() {
    if (!result) {
      return;
    }
    let next: Facts = { ...facts };
    const extraFacts: string[] = [];

    for (const question of result.route.missing_questions) {
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
    void runAnswer(next, confirmedUrgencies, confirmedAt ?? new Date().toISOString());
  }

  function clearSession() {
    abortRef.current?.abort();
    abortRef.current = null;
    setText("");
    setIntake(null);
    setFacts(emptyFacts());
    setConfirmedUrgencies([]);
    setConfirmedAt(null);
    setResult(null);
    setAnswerError(null);
    setIntakeError(null);
    setAnswers({});
    setAnswerBusy(false);
    setStep("landing");
  }

  const route = result?.route ?? null;
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
            <>
              {answerBusy ? <AnswerProgress onCancel={cancelAnswer} /> : null}
              <ConfirmationGate
                intake={intake}
                facts={facts}
                onFactsChange={setFacts}
                confirmedUrgencies={confirmedUrgencies}
                onUrgenciesChange={setConfirmedUrgencies}
                onConfirm={handleConfirm}
                onEditText={() => setStep("intake")}
                submitting={answerBusy}
                error={answerError}
              />
            </>
          ) : null}

          {step === "result" && result && route ? (
            <>
              {answerBusy ? <AnswerProgress onCancel={cancelAnswer} /> : null}

              {/*
                `published` is the ONLY field that authorises showing legal content.
                When it is false the answer was withheld on purpose and `answer`/`claims`
                are empty by design — so we explain why and show the route panels.
                We never fall back to rendering raw evidence as if it were an answer.
              */}
              {!answerBusy && !result.published ? (
                <div className="stack">
                  <WithheldNotice result={result} />

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
                      submitting={answerBusy}
                      error={answerError}
                    />
                  ) : null}

                  {route.priority === "standard" ? (
                    <section className="card">
                      <p className="card-subtle" style={{ marginBottom: 12 }}>
                        You can correct the facts and try again, or take this to a
                        person using the Legal Aid Finder in the side panel.
                      </p>
                      <div className="row row-end">
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={() => setStep("confirm")}
                        >
                          Correct my facts
                        </button>
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={retryAnswer}
                        >
                          Try again
                        </button>
                        <button
                          type="button"
                          className="btn-primary"
                          onClick={clearSession}
                        >
                          Start over
                        </button>
                      </div>
                    </section>
                  ) : null}
                </div>
              ) : null}

              {!answerBusy && result.published ? (
                <div className="stack">
                  <RouteContext route={route} />
                  <AnswerView
                    result={result}
                    facts={facts}
                    onEditFacts={() => setStep("confirm")}
                    onRestart={clearSession}
                  />
                </div>
              ) : null}
            </>
          ) : null}

          {step === "result" && !result && !answerBusy ? (
            <section className="card">
              <h2>Nothing to show yet</h2>
              <p>The result was lost. Please start again.</p>
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
