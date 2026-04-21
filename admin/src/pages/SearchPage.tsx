import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { SearchApi } from "@/api/endpoints";
import { Button, Card, Input, Label } from "@/components/ui";
import { useService } from "@/services/ServiceProvider";
import type { SearchResponse } from "@/api/types";

export default function SearchPage() {
  const { current: service } = useService();
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [docId, setDocId] = useState("");
  const [result, setResult] = useState<SearchResponse | null>(null);

  const run = useMutation({
    mutationFn: () =>
      SearchApi.run(service!.id, {
        query,
        top_k: topK,
        document_id: docId.trim() ? Number(docId) : undefined,
      }),
    onSuccess: (r) => setResult(r),
    onError: (e) => toast.error(e instanceof Error ? e.message : "Search failed"),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!service) {
      toast.error("No service selected");
      return;
    }
    setResult(null);
    run.mutate();
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Search</h1>

      <Card className="p-5">
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-4">
          <div className="md:col-span-2">
            <Label htmlFor="query">Query</Label>
            <Input
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search your documents…"
              required
            />
          </div>
          <div>
            <Label htmlFor="topk">Top K</Label>
            <Input
              id="topk"
              type="number"
              min={1}
              max={50}
              value={topK}
              onChange={(e) => setTopK(Math.max(1, Number(e.target.value)))}
            />
          </div>
          <div>
            <Label htmlFor="doc">Document ID (optional)</Label>
            <Input
              id="doc"
              value={docId}
              onChange={(e) => setDocId(e.target.value)}
              placeholder="e.g. 1"
            />
          </div>
          <div className="md:col-span-4">
            <Button type="submit" disabled={run.isPending || !service}>
              {run.isPending ? "Searching…" : "Search"}
            </Button>
          </div>
        </form>
      </Card>

      {result && (
        <Card>
          <div className="border-b border-slate-200 p-4 text-sm text-slate-600">
            {result.hits.length} hit{result.hits.length === 1 ? "" : "s"} for{" "}
            <span className="font-mono">{result.query}</span>
          </div>
          <ul className="divide-y divide-slate-100">
            {result.hits.map((h) => (
              <li key={`${h.document_id}:${h.ordinal}`} className="p-4">
                <div className="mb-1 flex flex-wrap items-center gap-2 text-sm">
                  <Link
                    to={`/documents/${h.document_id}`}
                    className="font-medium text-slate-900 hover:underline"
                  >
                    {h.document_title ?? `Document #${h.document_id}`}
                  </Link>
                  <span className="text-xs text-slate-500">
                    score {h.score.toFixed(3)} · chunk #{h.ordinal}
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-sm text-slate-700">{h.text}</p>
              </li>
            ))}
            {result.hits.length === 0 && (
              <li className="p-6 text-center text-sm text-slate-500">No matches.</li>
            )}
          </ul>
        </Card>
      )}
    </div>
  );
}
