import { useRef, useState } from "react";
import { ApiError, validateZip } from "./api";
import type { Finding, Severity, ValidateResponse } from "./types";
import "./App.css";

const SEVERITY_ORDER: Severity[] = ["error", "warning", "info"];

const SEVERITY_LABELS: Record<
  Severity,
  { heading: string; card: string; singular: string; plural: string }
> = {
  error: { heading: "Errors", card: "Error", singular: "error", plural: "errors" },
  warning: { heading: "Warnings", card: "Warning", singular: "warning", plural: "warnings" },
  info: { heading: "Info", card: "Info", singular: "note", plural: "notes" },
};

function isZip(file: File): boolean {
  return file.name.toLowerCase().endsWith(".zip");
}

function groupedFindings(findings: Finding[]): { severity: Severity; items: Finding[] }[] {
  return SEVERITY_ORDER
    .map((severity) => ({
      severity,
      items: findings.filter((item) => item.severity === severity),
    }))
    .filter((group) => group.items.length > 0);
}

export default function App() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<ValidateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setDragOver(false);
    setFileName(null);
    setChecking(false);
    setResult(null);
    setError(null);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  async function checkFile(file: File) {
    if (!isZip(file)) {
      setFileName(file.name);
      setResult(null);
      setError(
        "Please upload a .zip file. In MCreator, choose File then Export workspace to ZIP.",
      );
      return;
    }

    setFileName(file.name);
    setError(null);
    setResult(null);
    setChecking(true);
    try {
      const data = await validateZip(file);
      setResult(data);
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message);
      } else {
        setError("Something went wrong while checking the workspace. Please try again.");
      }
    } finally {
      setChecking(false);
    }
  }

  function onFiles(files: FileList | null) {
    const file = files?.[0];
    if (file) {
      void checkFile(file);
    }
  }

  const showDropzone = !checking && result === null && error === null;

  return (
    <div className="page">
      <header className="header">
        <h1>
          <span className="logo-mark" aria-hidden="true" />
          Mod Medic
        </h1>
        <p>
          Drop your MCreator workspace zip here and we will check it for common
          mistakes, like missing textures or broken links.
        </p>
      </header>

      {showDropzone && (
        <label
          className={`dropzone${dragOver ? " dropzone-active" : ""}`}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragOver(true);
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setDragOver(false);
          }}
          onDrop={(event) => {
            event.preventDefault();
            setDragOver(false);
            onFiles(event.dataTransfer.files);
          }}
        >
          <input
            ref={inputRef}
            className="file-input"
            type="file"
            accept=".zip,application/zip"
            onChange={(event) => onFiles(event.target.files)}
          />
          <span className="dropzone-title">Drop your .zip here</span>
          <span className="dropzone-hint">or click to choose a file from your computer</span>
          {fileName && <span className="filename">Chosen file: {fileName}</span>}
        </label>
      )}

      {checking && (
        <div className="panel loading" aria-busy="true" aria-live="polite">
          <div className="spinner" aria-hidden="true" />
          <p className="loading-title">Checking your workspace…</p>
          {fileName && <p className="filename">Chosen file: {fileName}</p>}
        </div>
      )}

      {error && !checking && (
        <div className="panel error-panel" role="alert">
          <h2>We could not check that file</h2>
          <p>{error}</p>
          <button type="button" className="reset" onClick={reset}>
            Check another workspace
          </button>
        </div>
      )}

      {result && !checking && (
        <div className="results">
          <div className="summary">
            <div>
              <h2 className="mod-name">{result.mod_name || "Untitled workspace"}</h2>
              <p className="counts-line">
                {result.element_count} elements · {result.variable_count} variables ·{" "}
                {result.texture_count} textures
              </p>
            </div>
            <div className="chips">
              {SEVERITY_ORDER.map((severity) => {
                const count = result.counts[severity];
                if (count === 0) {
                  return null;
                }
                const words = SEVERITY_LABELS[severity];
                return (
                  <span key={severity} className={`chip chip-${severity}`}>
                    {count} {count === 1 ? words.singular : words.plural}
                  </span>
                );
              })}
            </div>
          </div>

          {result.findings.length === 0 ? (
            <div className="panel success">
              <h2>Nice work!</h2>
              <p>No problems found. This workspace looks good.</p>
            </div>
          ) : (
            groupedFindings(result.findings).map((group) => (
              <section key={group.severity} className="finding-group">
                <h3 className={`group-heading group-${group.severity}`}>
                  {SEVERITY_LABELS[group.severity].heading}
                </h3>
                {group.items.map((finding, index) => (
                  <article
                    key={`${finding.rule_id}-${finding.element ?? "workspace"}-${index}`}
                    className={`card card-${finding.severity}`}
                  >
                    <div className="card-top">
                      <h4>{finding.element ?? "This workspace"}</h4>
                      <div className="card-tags">
                        <span className={`sev-label sev-${finding.severity}`}>
                          {SEVERITY_LABELS[finding.severity].card}
                        </span>
                        <span className="rule-tag">{finding.rule_id}</span>
                      </div>
                    </div>
                    <p>{finding.message}</p>
                    {finding.detail !== "" && (
                      <details>
                        <summary>Show details</summary>
                        <p className="detail">{finding.detail}</p>
                      </details>
                    )}
                  </article>
                ))}
              </section>
            ))
          )}

          <button type="button" className="reset" onClick={reset}>
            Check another workspace
          </button>
        </div>
      )}
    </div>
  );
}
