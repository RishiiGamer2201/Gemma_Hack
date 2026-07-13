import { useState } from "react";

import type { Facts } from "../api/types";
import { ChecklistPanel } from "./ChecklistPanel";
import { LegalAidPanel } from "./LegalAidPanel";

type Tab = "aid" | "checklist" | "privacy";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "aid", label: "Legal Aid" },
  { id: "checklist", label: "Checklist" },
  { id: "privacy", label: "Privacy" },
];

export function SidePanel({ facts }: { facts: Facts | null }) {
  const [tab, setTab] = useState<Tab>("aid");

  return (
    <aside aria-label="Tools" className="card" style={{ position: "sticky", top: 16 }}>
      <div className="tabs" role="tablist" aria-label="Support tools">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            id={`tab-${entry.id}`}
            className="tab"
            aria-selected={tab === entry.id}
            aria-controls={`panel-${entry.id}`}
            tabIndex={tab === entry.id ? 0 : -1}
            onClick={() => setTab(entry.id)}
            onKeyDown={(event) => {
              const index = TABS.findIndex((t) => t.id === tab);
              if (event.key === "ArrowRight") {
                event.preventDefault();
                setTab(TABS[(index + 1) % TABS.length].id);
              }
              if (event.key === "ArrowLeft") {
                event.preventDefault();
                setTab(TABS[(index - 1 + TABS.length) % TABS.length].id);
              }
            }}
          >
            {entry.label}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id="panel-aid"
        aria-labelledby="tab-aid"
        hidden={tab !== "aid"}
      >
        <LegalAidPanel
          bare
          heading="Legal Aid Finder"
          initialDistrict={facts?.location ?? ""}
          initialState={facts?.jurisdiction ?? ""}
        />
      </div>

      <div
        role="tabpanel"
        id="panel-checklist"
        aria-labelledby="tab-checklist"
        hidden={tab !== "checklist"}
      >
        <h3>Evidence Checklist</h3>
        <p className="card-subtle">
          What to gather before you approach an authority, a lawyer, or a court.
        </p>
        <ChecklistPanel />
      </div>

      <div
        role="tabpanel"
        id="panel-privacy"
        aria-labelledby="tab-privacy"
        hidden={tab !== "privacy"}
      >
        <h3>What stays on this device</h3>
        <ul style={{ paddingLeft: 18 }}>
          <li>Your description and the extracted facts stay in this browser tab's memory.</li>
          <li>They are sent only to the local server on 127.0.0.1, never to the internet.</li>
          <li>Uploaded images are read for text and are not stored by default.</li>
          <li>No cookies, no analytics, no telemetry, no remote fonts, no CDN.</li>
          <li>Closing the tab or clearing the session discards everything held in memory.</li>
        </ul>
        <p className="card-subtle">
          The "Clear session" button in the header wipes the facts, evidence, and
          uploaded text from this page immediately.
        </p>
      </div>
    </aside>
  );
}
