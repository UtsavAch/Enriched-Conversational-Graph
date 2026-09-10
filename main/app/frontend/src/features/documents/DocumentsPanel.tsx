import { useRef, useState } from "react";
import { ApiError } from "@/api/client";
import {
  useDeleteDocument,
  useDocumentSearch,
  useDocuments,
  useUploadDocument,
} from "@/api/queries";
import { Button } from "@/components/Button";
import { EmptyState, Spinner } from "@/components/States";
import "./Documents.css";

/**
 * External document sources.
 *
 * Deliberately its own panel rather than folded into the graph view. That
 * mirrors the architecture: document chunks are a separate store with a
 * separate retriever and a separate slice of the context budget, connected to
 * the conversation only through `grounded_by` provenance. Showing them inside
 * the graph would suggest an integration that does not exist.
 */
export function DocumentsPanel({
  conversationId,
}: {
  conversationId: string | null;
}) {
  const { data: documents, isLoading } = useDocuments();
  const upload = useUploadDocument(conversationId);
  const remove = useDeleteDocument();
  const fileRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const { data: hits, isFetching } = useDocumentSearch(query, searching);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) await upload.mutateAsync(file).catch(() => {});
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="documents">
      <p className="inspector-kind">external documents</p>
      <h2 className="inspector-title">Sources</h2>
      <p className="inspector-lede">
        PDFs and text files retrieved alongside the conversation memory, on
        their own context budget.
      </p>
      {conversationId && (
        <p className="field-note">
          Uploads here are also archived into <code>{conversationId}</code>'s
          documents folder.
        </p>
      )}

      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.txt,.md"
        onChange={handleFile}
        className="sr-only"
        id="doc-upload"
      />
      <Button
        variant="primary"
        onClick={() => fileRef.current?.click()}
        disabled={upload.isPending}
      >
        {upload.isPending ? "Ingesting…" : "Add a document"}
      </Button>

      {upload.isError && (
        <p className="health-note health-warn">
          {/* `.message` on an ApiError is just "400 Bad Request" - `.detail` is
              the actual reason from the backend (e.g. why a PDF was rejected). */}
          {(upload.error as ApiError).detail || (upload.error as Error).message}
        </p>
      )}

      <div className="inspector-divider" />

      {isLoading ? (
        <Spinner />
      ) : !documents?.length ? (
        <EmptyState
          title="No documents yet"
          hint="Add a PDF to ground answers in external material."
        />
      ) : (
        <ul className="doc-list">
          {documents.map((doc) => (
            <li key={doc.id} className="doc-item">
              <div className="doc-main">
                <span className="doc-title">{doc.title}</span>
                <span className="doc-meta">
                  {doc.id} · {doc.n_chunks} chunks · {doc.source_type}
                </span>
              </div>
              <button
                className="doc-remove"
                aria-label={`Remove ${doc.title}`}
                onClick={() => remove.mutate(doc.id)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      {Boolean(documents?.length) && (
        <>
          <div className="inspector-divider" />
          <p className="field-label">Test retrieval</p>
          <p className="field-note" style={{ marginBottom: 6 }}>
            Preview what the retriever returns for a query. Useful when a
            grounded answer looks wrong and you need to know whether retrieval
            or generation was at fault.
          </p>
          <div className="doc-search">
            <input
              value={query}
              placeholder="Search the documents…"
              onChange={(e) => {
                setQuery(e.target.value);
                setSearching(false);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") setSearching(true);
              }}
            />
            <Button size="sm" onClick={() => setSearching(true)}>
              Search
            </Button>
          </div>

          {isFetching && <Spinner />}
          {hits?.map((hit) => (
            <div key={hit.chunk_id} className="doc-hit">
              <div className="doc-hit-head">
                <span className="doc-hit-id">{hit.chunk_id}</span>
                <span className="doc-hit-score">{hit.score.toFixed(3)}</span>
              </div>
              <p className="doc-hit-source">
                {hit.source_title}
                {hit.page !== null ? `, p.${hit.page}` : ""}
              </p>
              <p className="doc-hit-text">{hit.text.slice(0, 260)}…</p>
            </div>
          ))}
          {hits?.length === 0 && searching && (
            <p className="health-note">No matches.</p>
          )}
        </>
      )}
    </div>
  );
}
