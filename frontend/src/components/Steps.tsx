export type StepId = "landing" | "intake" | "confirm" | "result";

const STEPS: Array<{ id: StepId; label: string }> = [
  { id: "landing", label: "1. Privacy & limits" },
  { id: "intake", label: "2. Your situation" },
  { id: "confirm", label: "3. Confirm the facts" },
  { id: "result", label: "4. Law & next steps" },
];

export function Steps({ current }: { current: StepId }) {
  const currentIndex = STEPS.findIndex((step) => step.id === current);

  return (
    <nav aria-label="Progress">
      <ol className="steps">
        {STEPS.map((step, index) => {
          const state =
            index < currentIndex ? "done" : index === currentIndex ? "current" : "todo";
          return (
            <li key={step.id} data-state={state}>
              {state === "done" ? <span aria-hidden="true">✓</span> : null}
              {step.label}
              {state === "current" ? (
                <span className="visually-hidden"> (current step)</span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
