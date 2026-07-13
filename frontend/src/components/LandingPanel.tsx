interface Props {
  onStart: () => void;
}

export function LandingPanel({ onStart }: Props) {
  return (
    <section className="card" aria-labelledby="landing-heading">
      <h2 id="landing-heading">Before you start</h2>
      <p>
        Nyaya Navigator helps you understand which Indian law may apply to your
        situation, what official text actually says, and what practical next
        steps and legal-aid options exist. It is a navigation aid, not a lawyer.
      </p>

      <hr className="divider" />

      <div className="grid-2">
        <div>
          <h3>Everything stays on this computer</h3>
          <ul>
            <li>
              The interface talks only to a server running on this machine
              (127.0.0.1). No cloud, no accounts, no analytics.
            </li>
            <li>
              The language model runs locally. Your description of the incident
              is never uploaded.
            </li>
            <li>
              Uploaded photos are used to read text and are not stored by
              default. Clearing the session removes what is held in memory.
            </li>
            <li>
              It is designed to work with Wi-Fi switched off. That is the
              intended way to use it.
            </li>
          </ul>
        </div>

        <div>
          <h3>What it will not do</h3>
          <ul>
            <li>
              It will not tell you whether you will win, and it will not produce
              case-strength percentages.
            </li>
            <li>
              It will not invent sections, deadlines, or helpline numbers. If it
              cannot find official support, it says so and stops.
            </li>
            <li>
              It quotes the law verbatim with an official source link and an
              effective date, so you can check it yourself.
            </li>
            <li>
              If your situation looks urgent or unsafe, it will point you to
              human help first, before any legal explanation.
            </li>
          </ul>
        </div>
      </div>

      <hr className="divider" />

      <h3>How it works</h3>
      <ol>
        <li>You describe what happened, in English, Hindi, or Hinglish.</li>
        <li>
          It restates the facts back to you. <strong>You must confirm or fix
          them</strong> before anything else happens.
        </li>
        <li>It checks for urgency, then retrieves the official law that applies.</li>
        <li>
          You get the source text, warnings about what is not proven, an evidence
          checklist, and legal-aid contacts.
        </li>
      </ol>

      <div className="row row-end" style={{ marginTop: 16 }}>
        <button type="button" className="btn-primary" onClick={onStart}>
          I understand — describe my situation
        </button>
      </div>
    </section>
  );
}
