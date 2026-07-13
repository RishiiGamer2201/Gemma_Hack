import { useCallback, useEffect, useState } from "react";

import { getChecklist, getChecklists } from "../api/client";
import type { ChecklistSummary, ChecklistTemplate } from "../api/types";
import { Empty, ErrorNotice, Progress } from "./Feedback";

function labelFor(summary: ChecklistSummary): string {
  return summary.title ?? summary.template_id.replace(/_/g, " ");
}

export function ChecklistPanel() {
  const [templates, setTemplates] = useState<ChecklistSummary[]>([]);
  const [selected, setSelected] = useState("");
  const [template, setTemplate] = useState<ChecklistTemplate | null>(null);
  const [ticked, setTicked] = useState<Record<string, boolean>>({});
  const [loadingIndex, setLoadingIndex] = useState(false);
  const [loadingTemplate, setLoadingTemplate] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const loadIndex = useCallback(async () => {
    setLoadingIndex(true);
    setError(null);
    try {
      setTemplates(await getChecklists());
    } catch (caught) {
      setError(caught);
    } finally {
      setLoadingIndex(false);
    }
  }, []);

  useEffect(() => {
    void loadIndex();
  }, [loadIndex]);

  const loadTemplate = useCallback(async (templateId: string) => {
    if (!templateId) {
      setTemplate(null);
      return;
    }
    setLoadingTemplate(true);
    setError(null);
    try {
      const loaded = await getChecklist(templateId);
      setTemplate(loaded);
      setTicked({});
    } catch (caught) {
      setError(caught);
      setTemplate(null);
    } finally {
      setLoadingTemplate(false);
    }
  }, []);

  /** Exports the checklist only. The case narrative is never included. */
  function exportJson() {
    if (!template) {
      return;
    }
    const payload = {
      template_id: template.template_id,
      title: template.title,
      guidance_label: template.guidance_label,
      exported_at: new Date().toISOString(),
      items: template.items.map((item) => ({
        item_id: item.item_id,
        label: item.label,
        sensitive: item.sensitive,
        collected: Boolean(ticked[item.item_id]),
      })),
      note: "Checklist only. No case facts are included in this file.",
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${template.template_id}_checklist.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const doneCount = template
    ? template.items.filter((item) => ticked[item.item_id]).length
    : 0;

  return (
    <div>
      <div className="field">
        <label htmlFor="checklist-select">Choose a checklist</label>
        <select
          id="checklist-select"
          value={selected}
          disabled={loadingIndex}
          onChange={(event) => {
            setSelected(event.target.value);
            void loadTemplate(event.target.value);
          }}
        >
          <option value="">Select…</option>
          {templates.map((summary) => (
            <option key={summary.template_id} value={summary.template_id}>
              {labelFor(summary)}
            </option>
          ))}
        </select>
      </div>

      {loadingIndex ? <Progress label="Loading checklists…" /> : null}
      {loadingTemplate ? <Progress label="Loading items…" /> : null}

      <ErrorNotice
        error={error}
        title="Checklist unavailable"
        onRetry={() => {
          if (selected) {
            void loadTemplate(selected);
          } else {
            void loadIndex();
          }
        }}
      />

      {!loadingIndex && templates.length === 0 && !error ? (
        <Empty>No checklist templates are available from the local backend.</Empty>
      ) : null}

      {template ? (
        <>
          <h3>{template.title}</h3>
          <p className="card-subtle">{template.guidance_label}</p>

          <p className="hint">
            {doneCount} of {template.items.length} collected. Items marked
            sensitive may contain personal information — share them only with
            the authority or lawyer who needs them.
          </p>

          <ul style={{ listStyle: "none", padding: 0, margin: "8px 0" }}>
            {template.items.map((item) => (
              <li className="checklist-item" key={item.item_id}>
                <input
                  type="checkbox"
                  id={`item-${item.item_id}`}
                  checked={Boolean(ticked[item.item_id])}
                  onChange={(event) =>
                    setTicked((current) => ({
                      ...current,
                      [item.item_id]: event.target.checked,
                    }))
                  }
                />
                <label htmlFor={`item-${item.item_id}`}>{item.label}</label>
                {item.sensitive ? (
                  <span className="tag-sensitive">sensitive</span>
                ) : null}
              </li>
            ))}
          </ul>

          <div className="row row-end">
            <button type="button" className="btn-secondary btn-small" onClick={exportJson}>
              Export checklist (JSON)
            </button>
          </div>
          <p className="hint">
            The export contains the checklist and your ticks only — never your
            case description.
          </p>
        </>
      ) : null}
    </div>
  );
}
