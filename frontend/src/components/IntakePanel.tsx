import { useRef, useState } from "react";

import {
  ALLOWED_UPLOAD_TYPES,
  MAX_UPLOAD_BYTES,
  postOcr,
} from "../api/client";
import type { OcrResponse } from "../api/types";
import { ErrorNotice, Progress } from "./Feedback";
import { MicRecorder } from "./MicRecorder";

interface Props {
  text: string;
  onTextChange: (value: string) => void;
  onSubmit: () => void;
  submitting: boolean;
  submitError: unknown;
  onBack: () => void;
}

const MIN_CHARS = 15;

export function IntakePanel({
  text,
  onTextChange,
  onSubmit,
  submitting,
  submitError,
  onBack,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [ocrBusy, setOcrBusy] = useState(false);
  const [ocrError, setOcrError] = useState<unknown>(null);
  const [ocrResult, setOcrResult] = useState<OcrResponse | null>(null);
  const [lastFileName, setLastFileName] = useState<string | null>(null);

  const tooShort = text.trim().length < MIN_CHARS;

  async function handleFile(file: File | undefined) {
    if (!file) {
      return;
    }
    setOcrError(null);
    setOcrResult(null);
    setLastFileName(file.name);
    setOcrBusy(true);
    try {
      const result = await postOcr(file);
      setOcrResult(result);
      const recognized = result.text.trim();
      if (recognized) {
        const separator = text.trim() ? "\n\n" : "";
        onTextChange(`${text}${separator}${recognized}`);
      }
    } catch (error) {
      setOcrError(error);
    } finally {
      setOcrBusy(false);
      // Allow re-selecting the same file after a correction.
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  // mean_confidence_percent is nullable in the backend contract.
  const confidence = ocrResult?.mean_confidence_percent ?? null;
  const lowConfidence = confidence !== null && confidence < 75;

  return (
    <section className="card" aria-labelledby="intake-heading">
      <div className="card-title">
        <h2 id="intake-heading">Describe what happened</h2>
        <button type="button" className="btn-link btn-small" onClick={onBack}>
          Back to overview
        </button>
      </div>

      <p className="card-subtle">
        Write in English, Hindi, or Hinglish — whichever is easiest. Include
        dates, who was involved, the place, and any document you have. Do not
        include more personal detail than you need to.
      </p>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!tooShort && !submitting) {
            onSubmit();
          }
        }}
      >
        <div className="field">
          <label htmlFor="intake-text">Your situation</label>
          <textarea
            id="intake-text"
            value={text}
            onChange={(event) => onTextChange(event.target.value)}
            placeholder="e.g. Meri company ne pichhle 3 mahine ki salary nahi di. Main Delhi mein kaam karta hoon. Last payment 10 April 2026 ko mili thi."
            rows={9}
            aria-describedby="intake-help"
            disabled={submitting}
          />
          <p className="hint" id="intake-help">
            {text.trim().length} characters. At least {MIN_CHARS} characters are
            needed before the facts can be extracted.
          </p>
        </div>

        <div className="field">
          <span className="field-label">Or speak your situation (optional)</span>
          <MicRecorder
            language="auto"
            disabled={submitting || ocrBusy}
            onTranscript={(spoken) => {
              const separator = text.trim() ? "\n\n" : "";
              onTextChange(`${text}${separator}${spoken}`);
            }}
          />
          <p className="hint">
            Up to one minute. The recording is transcribed on this machine and the
            text is added above so you can correct it. The audio is not stored.
          </p>
        </div>

        <hr className="divider" />

        <div className="field">
          <label htmlFor="intake-file">
            Or upload a photo of a notice, FIR, or letter (optional)
          </label>
          <input
            ref={fileInputRef}
            id="intake-file"
            type="file"
            accept={ALLOWED_UPLOAD_TYPES.join(",")}
            onChange={(event) => void handleFile(event.target.files?.[0])}
            disabled={ocrBusy || submitting}
            aria-describedby="intake-file-help"
          />
          <p className="hint" id="intake-file-help">
            PNG or JPEG, up to {Math.round(MAX_UPLOAD_BYTES / (1024 * 1024))} MB.
            The text is read on this machine and added to the box above so you
            can correct it. The image itself is not stored.
          </p>
        </div>

        {ocrBusy ? (
          <Progress
            label="Reading the image…"
            detail={lastFileName ? `Processing ${lastFileName} locally` : undefined}
          />
        ) : null}

        <ErrorNotice
          error={ocrError}
          title="Could not read that image"
          onRetry={() => {
            setOcrError(null);
            fileInputRef.current?.click();
          }}
        />

        {ocrResult ? (
          <div
            className={`alert ${lowConfidence ? "alert-warn" : "alert-info"}`}
            role="status"
          >
            <h3>
              {lowConfidence
                ? "Text read, but confidence is low"
                : "Text read from the image"}
            </h3>
            <p>
              Recognition confidence:{" "}
              <strong>
                {confidence === null ? "not reported" : `${confidence.toFixed(1)}%`}
              </strong>{" "}
              ({ocrResult.width}×{ocrResult.height} px).{" "}
              {ocrResult.text.trim()
                ? "The recognised text was added to the box above."
                : "No readable text was found in the image."}
            </p>
            <p>
              <strong>Please read it and correct any mistakes</strong> before
              continuing. OCR errors in dates, names, and section numbers change
              the legal answer.
            </p>
          </div>
        ) : null}

        <ErrorNotice error={submitError} title="Fact extraction failed" onRetry={onSubmit} />

        {submitting ? (
          <Progress
            label="Extracting facts…"
            detail="Detecting language and urgency signals on this machine"
          />
        ) : null}

        <div className="row row-end">
          <button
            type="submit"
            className="btn-primary"
            disabled={tooShort || submitting || ocrBusy}
          >
            {submitting ? "Working…" : "Extract the facts"}
          </button>
        </div>
        {tooShort ? (
          <p className="hint" style={{ textAlign: "right" }}>
            Add a little more detail to continue.
          </p>
        ) : null}
      </form>
    </section>
  );
}
