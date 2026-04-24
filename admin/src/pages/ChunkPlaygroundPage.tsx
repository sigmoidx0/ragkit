import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import { IngestApi } from "@/api/endpoints";
import { Button, Card, Input, Label } from "@/components/ui";
import { ChunkConfigForm } from "@/components/ChunkConfigForm";
import type { ChunkConfig, ChunkPreviewChunk, ChunkPreviewResponse } from "@/api/types";

type Tab = "markdown" | "chunks";

function ChunkCard({ chunk, index }: { chunk: ChunkPreviewChunk; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const preview = chunk.text.length > 300 ? chunk.text.slice(0, 300) + "…" : chunk.text;
  const metaEntries = Object.entries(chunk.metadata).filter(([, v]) => v != null);

  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center gap-2 text-xs text-[#A0AEC0]">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-teal-400 text-[10px] font-bold text-white">
          {index + 1}
        </span>
        <span>{chunk.char_count.toLocaleString()} chars</span>
        {metaEntries.map(([k, v]) => (
          <span key={k} className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[10px]">
            {k}: {String(v)}
          </span>
        ))}
      </div>
      <p className="whitespace-pre-wrap text-sm text-[#2D3748]">
        {expanded ? chunk.text : preview}
      </p>
      {chunk.text.length > 300 && (
        <button
          className="mt-1 text-xs text-teal-500 hover:underline"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

export default function ChunkPlaygroundPage() {
  const [file, setFile] = useState<File | null>(null);
  const [chunkConfig, setChunkConfig] = useState<ChunkConfig>({ strategy: "recursive" });
  const [result, setResult] = useState<ChunkPreviewResponse | null>(null);
  const [tab, setTab] = useState<Tab>("chunks");

  const run = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      fd.set("file", file!);
      fd.set("chunk_config", JSON.stringify(chunkConfig));
      return IngestApi.previewChunks(fd);
    },
    onSuccess: (r) => {
      setResult(r);
      setTab("chunks");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Preview failed"),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!file) {
      toast.error("Choose a file first");
      return;
    }
    run.mutate();
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        {/* ── Config panel ─────────────────────────────── */}
        <Card className="h-fit p-5 lg:sticky lg:top-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-[#A0AEC0]">
            Chunk Playground
          </h2>
          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <Label htmlFor="pg-file">File</Label>
              <Input
                id="pg-file"
                type="file"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                required
              />
            </div>

            <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
              <ChunkConfigForm value={chunkConfig} onChange={setChunkConfig} />
            </div>

            <Button type="submit" disabled={run.isPending || !file} className="w-full">
              {run.isPending ? "Processing…" : "Run Preview"}
            </Button>
          </form>
        </Card>

        {/* ── Results panel ────────────────────────────── */}
        <div className="space-y-4">
          {!result && !run.isPending && (
            <Card className="flex h-64 items-center justify-center text-sm text-[#A0AEC0]">
              Upload a file and click Run Preview to see results.
            </Card>
          )}

          {run.isPending && (
            <Card className="flex h-64 items-center justify-center text-sm text-[#A0AEC0]">
              Processing…
            </Card>
          )}

          {result && (
            <>
              {/* Tab bar */}
              <div className="flex items-center gap-1 rounded-xl border border-gray-100 bg-white p-1 shadow-sm w-fit">
                {(["chunks", "markdown"] as Tab[]).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={`rounded-lg px-4 py-1.5 text-sm font-semibold transition-colors ${
                      tab === t
                        ? "bg-teal-400 text-white shadow-sm"
                        : "text-[#A0AEC0] hover:text-[#2D3748]"
                    }`}
                  >
                    {t === "chunks"
                      ? `Chunks (${result.total_chunks})`
                      : "Markdown"}
                  </button>
                ))}
              </div>

              {/* Chunks tab */}
              {tab === "chunks" && (
                <div className="space-y-3">
                  {result.chunks.map((chunk, i) => (
                    <ChunkCard key={chunk.ordinal} chunk={chunk} index={i} />
                  ))}
                  {result.chunks.length === 0 && (
                    <Card className="p-6 text-center text-sm text-[#A0AEC0]">
                      No chunks produced.
                    </Card>
                  )}
                </div>
              )}

              {/* Markdown tab */}
              {tab === "markdown" && (
                <Card className="p-5">
                  {result.markdown_truncated && (
                    <p className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                      Preview truncated to 50,000 characters.
                    </p>
                  )}
                  <div className="prose prose-sm max-w-none overflow-auto rounded border border-gray-100 bg-gray-50 p-4 max-h-[70vh]">
                    <ReactMarkdown>{result.markdown}</ReactMarkdown>
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
