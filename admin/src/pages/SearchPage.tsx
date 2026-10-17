import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { DocumentSetsApi, PipelineApi, SearchApi } from "@/api/endpoints";
import { Button, Card, FormField, Input } from "@/components/ui";
import { useWorkspace } from "@/workspace/WorkspaceProvider";
import type { SearchResponse } from "@/api/types";

export default function SearchPage() {
  const { workspace } = useWorkspace();
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [docId, setDocId] = useState("");
  const [pipelineId, setPipelineId] = useState<number | null>(null);
  const [setIds, setSetIds] = useState<number[]>([]);
  const [result, setResult] = useState<SearchResponse | null>(null);

  const { data: activePipelines = [] } = useQuery({
    queryKey: ["pipelines-active", workspace?.id],
    queryFn: () => PipelineApi.list(workspace!.id),
    enabled: !!workspace,
    staleTime: 30_000,
  });

  const { data: documentSets = [] } = useQuery({
    queryKey: ["document-sets", workspace?.id],
    queryFn: () => DocumentSetsApi.list(workspace!.id),
    enabled: !!workspace,
  });

  const run = useMutation({
    mutationFn: () =>
      SearchApi.run(workspace!.id, {
        query,
        top_k: topK,
        document_id: docId.trim() ? Number(docId) : undefined,
        pipeline_id: pipelineId,
        document_set_ids: setIds.length ? setIds : null,
      }),
    onSuccess: (r) => setResult(r),
    onError: (e) => toast.error(e instanceof Error ? e.message : "Search failed"),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!workspace) {
      toast.error("No workspace selected");
      return;
    }
    setResult(null);
    run.mutate();
  };

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-4">
          <FormField label="Query" htmlFor="query" className="md:col-span-2">
            <Input
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search your documents…"
              required
            />
          </FormField>
          <FormField label="Top K" htmlFor="topk">
            <Input
              id="topk"
              type="number"
              min={1}
              max={50}
              value={topK}
              onChange={(e) => setTopK(Math.max(1, Number(e.target.value)))}
            />
          </FormField>
          <FormField label="Document ID (optional)" htmlFor="doc">
            <Input
              id="doc"
              value={docId}
              onChange={(e) => setDocId(e.target.value)}
              placeholder="e.g. 1"
            />
          </FormField>
          {documentSets.length > 0 && (
            // Same scope an agent with these sets selected would search.
            <div className="md:col-span-4">
              <p className="mb-1 text-xs font-semibold text-[#2D3748] dark:text-gray-200">
                Document sets <span className="font-normal text-gray-400">— none selected searches the whole workspace; an agent with these sets searches the same documents</span>
              </p>
              <div className="flex flex-wrap gap-1.5">
                {documentSets.map((ds) => {
                  const on = setIds.includes(ds.id);
                  return (
                    <button
                      key={ds.id}
                      type="button"
                      onClick={() => setSetIds(on ? setIds.filter((i) => i !== ds.id) : [...setIds, ds.id])}
                      className={
                        on
                          ? "rounded-lg border border-teal-400 bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-700 dark:bg-teal-900/30 dark:text-teal-300"
                          : "rounded-lg border border-gray-200 px-2.5 py-1 text-xs text-gray-500 hover:border-gray-300 dark:border-gray-600"
                      }
                    >
                      {ds.name} <span className="font-mono text-gray-400">{ds.document_ids.length}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          {activePipelines.length > 0 && (
            <FormField label="Pipeline (optional)" htmlFor="pipeline" className="md:col-span-2">
              <select
                id="pipeline"
                value={pipelineId ?? ""}
                onChange={(e) => setPipelineId(e.target.value ? Number(e.target.value) : null)}
                className="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-teal-300"
              >
                <option value="">Default (no pipeline)</option>
                {activePipelines.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </FormField>
          )}
          <div className="md:col-span-4">
            <Button type="submit" disabled={run.isPending || !workspace}>
              {run.isPending ? "Searching…" : "Search"}
            </Button>
          </div>
        </form>
      </Card>

      {result && (
        <Card>
          <div className="border-b border-gray-100 p-4 text-sm text-[#A0AEC0]">
            {result.hits.length} hit{result.hits.length === 1 ? "" : "s"} for{" "}
            <span className="font-mono">{result.query}</span>
          </div>
          <ul className="divide-y divide-gray-100">
            {result.hits.map((h) => (
              <li key={`${h.document_id}:${h.ordinal}`} className="p-4">
                <div className="mb-1 flex flex-wrap items-center gap-2 text-sm">
                  <Link
                    to={`/documents/${h.document_id}`}
                    className="font-medium text-[#2D3748] hover:underline"
                  >
                    {h.document_title ?? `Document #${h.document_id}`}
                  </Link>
                  <span className="text-xs text-[#A0AEC0]">
                    score {h.score.toFixed(3)} · chunk #{h.ordinal}
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-sm text-[#2D3748]">{h.text}</p>
              </li>
            ))}
            {result.hits.length === 0 && (
              <li className="p-6 text-center text-sm text-[#A0AEC0]">No matches.</li>
            )}
          </ul>
        </Card>
      )}
    </div>
  );
}
