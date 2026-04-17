import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DocumentsApi } from "@/api/endpoints";
import {
  Badge,
  Button,
  Card,
  ErrorBox,
  Input,
  Label,
  Textarea,
} from "@/components/ui";
import type { DocumentStatus } from "@/api/types";

function statusTone(s: DocumentStatus): "green" | "amber" | "red" {
  if (s === "ready") return "green";
  if (s === "pending") return "amber";
  return "red";
}

export default function DocumentsPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 25;

  const listQuery = useQuery({
    queryKey: ["documents", { q, limit, offset }],
    queryFn: () => DocumentsApi.list({ q: q || undefined, limit, offset }),
  });

  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const createDoc = useMutation({
    mutationFn: (fd: FormData) => DocumentsApi.create(fd),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["documents"] });
      setFile(null);
      setTitle("");
      setDescription("");
    },
  });

  const onUpload = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (!file) {
      setError("Please choose a file");
      return;
    }
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.set("file", file);
      fd.set("title", title);
      if (description) fd.set("description", description);
      await createDoc.mutateAsync(fd);
    } catch (err) {
      setError(err instanceof Error ? err.message : "upload failed");
    } finally {
      setUploading(false);
    }
  };

  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Documents</h1>
        <div className="text-sm text-slate-500">{total} total</div>
      </div>

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">
          Upload
        </h2>
        <form onSubmit={onUpload} className="grid gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="file">File</Label>
            <Input
              id="file"
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
          </div>
          <div className="md:col-span-2">
            <Label htmlFor="description">Description (optional)</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </div>
          {error && (
            <div className="md:col-span-2">
              <ErrorBox message={error} />
            </div>
          )}
          <div className="md:col-span-2">
            <Button type="submit" disabled={uploading}>
              {uploading ? "Uploading…" : "Upload"}
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <div className="flex items-center justify-between gap-3 border-b border-slate-200 p-4">
          <Input
            placeholder="Filter by title…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
            className="max-w-sm"
          />
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <Button
              variant="secondary"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
            >
              Previous
            </Button>
            <span>
              {offset + 1}–{Math.min(offset + items.length, total)}
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={offset + items.length >= total}
              onClick={() => setOffset(offset + limit)}
            >
              Next
            </Button>
          </div>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Title</th>
              <th className="px-4 py-2">File</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Created</th>
            </tr>
          </thead>
          <tbody>
            {listQuery.isLoading && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                  Loading…
                </td>
              </tr>
            )}
            {!listQuery.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                  No documents yet.
                </td>
              </tr>
            )}
            {items.map((d) => (
              <tr key={d.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2">
                  <Link
                    to={`/documents/${d.id}`}
                    className="font-medium text-slate-900 hover:underline"
                  >
                    {d.title}
                  </Link>
                  {d.description && (
                    <div className="text-xs text-slate-500 line-clamp-1">{d.description}</div>
                  )}
                </td>
                <td className="px-4 py-2 text-slate-600">{d.source_filename}</td>
                <td className="px-4 py-2">
                  <Badge tone={statusTone(d.status)}>{d.status}</Badge>
                </td>
                <td className="px-4 py-2 text-slate-500">
                  {new Date(d.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
