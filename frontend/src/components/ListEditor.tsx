import { useState } from "react";

interface Props {
  id: string;
  label: string;
  hint?: string;
  placeholder?: string;
  values: string[];
  onChange: (values: string[]) => void;
  disabled?: boolean;
}

/** Editable string list used for parties, material facts, and documents. */
export function ListEditor({
  id,
  label,
  hint,
  placeholder,
  values,
  onChange,
  disabled,
}: Props) {
  const [draft, setDraft] = useState("");

  function add() {
    const value = draft.trim();
    if (!value) {
      return;
    }
    onChange([...values, value]);
    setDraft("");
  }

  return (
    <fieldset
      className="field"
      style={{ border: "none", padding: 0, margin: "0 0 12px" }}
    >
      <legend style={{ padding: 0 }}>
        <span
          style={{ fontWeight: 600, fontSize: "0.85rem" }}
          id={`${id}-label`}
        >
          {label}
        </span>
      </legend>
      {hint ? <p className="hint">{hint}</p> : null}

      {values.length === 0 ? (
        <p className="empty">Nothing added yet.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: "6px 0" }}>
          {values.map((value, index) => (
            <li key={`${id}-${index}`} className="list-editor-item">
              <input
                type="text"
                value={value}
                aria-label={`${label} ${index + 1}`}
                disabled={disabled}
                onChange={(event) => {
                  const next = [...values];
                  next[index] = event.target.value;
                  onChange(next);
                }}
              />
              <button
                type="button"
                className="btn-secondary btn-small"
                disabled={disabled}
                onClick={() => onChange(values.filter((_, i) => i !== index))}
              >
                Remove
                <span className="visually-hidden"> {label} entry {index + 1}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="list-editor-item">
        <input
          id={`${id}-new`}
          type="text"
          value={draft}
          placeholder={placeholder}
          disabled={disabled}
          aria-label={`Add to ${label}`}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              add();
            }
          }}
        />
        <button
          type="button"
          className="btn-secondary btn-small"
          onClick={add}
          disabled={disabled || !draft.trim()}
        >
          Add
        </button>
      </div>
    </fieldset>
  );
}
