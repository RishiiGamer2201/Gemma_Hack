import { useCallback, useEffect, useRef, useState } from "react";

import { pcmToWav, postTranscribe } from "../api/client";
import type { TranscriptResponse } from "../api/types";
import { ErrorNotice, Progress } from "./Feedback";

/**
 * Voice input. The clip is captured as raw PCM in the browser, encoded to a
 * 16 kHz mono WAV, and sent only to the loopback backend, which transcribes it on
 * this machine. The transcript is a DRAFT: it lands in the situation box for the
 * user to read and correct, and never proceeds on its own.
 *
 * getUserMedia and AudioContext are standard browser APIs and need no network. The
 * microphone stream is stopped and released the moment recording ends.
 */

const MAX_SECONDS = 60;

interface Props {
  language: "auto" | "hi" | "en";
  disabled?: boolean;
  onTranscript: (text: string) => void;
}

type Phase = "idle" | "recording" | "transcribing";

export function MicRecorder({ language, disabled, onTranscript }: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<TranscriptResponse | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const chunksRef = useRef<Float32Array[]>([]);
  const sampleRateRef = useRef<number>(48_000);
  const timerRef = useRef<number | null>(null);

  const teardown = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    processorRef.current = null;
    sourceRef.current = null;
    if (contextRef.current && contextRef.current.state !== "closed") {
      void contextRef.current.close();
    }
    contextRef.current = null;
    // Releasing the stream turns off the browser's recording indicator.
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => teardown, [teardown]);

  const finish = useCallback(async () => {
    teardown();
    const chunks = chunksRef.current;
    chunksRef.current = [];
    const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    if (total === 0) {
      setPhase("idle");
      setError(
        new Error("No audio was captured. Check the microphone permission and try again."),
      );
      return;
    }
    const merged = new Float32Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }

    setPhase("transcribing");
    try {
      const wav = pcmToWav(merged, sampleRateRef.current);
      const transcript = await postTranscribe(wav, language);
      setResult(transcript);
      if (transcript.transcript.trim()) {
        onTranscript(transcript.transcript.trim());
      }
    } catch (err) {
      setError(err);
    } finally {
      setPhase("idle");
    }
  }, [language, onTranscript, teardown]);

  const start = useCallback(async () => {
    setError(null);
    setResult(null);
    chunksRef.current = [];
    setElapsed(0);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const context = new AudioContext();
      contextRef.current = context;
      sampleRateRef.current = context.sampleRate;
      const source = context.createMediaStreamSource(stream);
      sourceRef.current = source;
      const processor = context.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      processor.onaudioprocess = (event) => {
        // Copy: the event buffer is reused by the audio thread.
        chunksRef.current.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      };
      source.connect(processor);
      processor.connect(context.destination);
      setPhase("recording");
      timerRef.current = window.setInterval(() => {
        setElapsed((seconds) => {
          const next = seconds + 1;
          if (next >= MAX_SECONDS) {
            void finish();
          }
          return next;
        });
      }, 1_000);
    } catch (err) {
      teardown();
      setPhase("idle");
      setError(
        err instanceof DOMException && err.name === "NotAllowedError"
          ? new Error(
              "Microphone permission was denied. Allow it in the browser, or type instead.",
            )
          : err,
      );
    }
  }, [finish, teardown]);

  const supported =
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof AudioContext !== "undefined";

  if (!supported) {
    return (
      <p className="hint">
        Voice input is not available in this browser. Please type your situation instead.
      </p>
    );
  }

  return (
    <div className="mic">
      <div className="row" style={{ alignItems: "center", gap: 12 }}>
        {phase === "recording" ? (
          <button type="button" className="btn-danger" onClick={() => void finish()}>
            ■ Stop and transcribe ({MAX_SECONDS - elapsed}s left)
          </button>
        ) : (
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void start()}
            disabled={disabled || phase === "transcribing"}
          >
            🎤 Speak your situation
          </button>
        )}
        {phase === "recording" ? (
          <span className="recording-dot" aria-hidden="true" />
        ) : null}
      </div>

      {phase === "transcribing" ? (
        <Progress label="Transcribing on this machine…" detail="No audio left the device" />
      ) : null}

      <ErrorNotice error={error} title="Could not use the microphone" />

      {result ? (
        <div className="alert alert-info" role="status">
          <p style={{ marginBottom: 0 }}>
            {result.transcript.trim()
              ? "Transcript added to the box above — please read it and fix any mistakes before continuing."
              : "No speech was recognised. Try again, or type your situation."}{" "}
            {result.detected_language ? (
              <span className="card-subtle">
                (heard as {result.detected_language.toUpperCase()})
              </span>
            ) : null}
          </p>
        </div>
      ) : null}
    </div>
  );
}
