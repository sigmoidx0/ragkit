import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import { DocumentsApi } from "@/api/endpoints";
import { Badge, Button, Card, Input, Label, formatBytes } from "@/components/ui";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useService } from "@/services/ServiceProvider";
import type { DocumentStatus } from "@/api/types";

function statusTone(s: DocumentStatus): "green" | "amber" | "red" {
  if (s === "indexed") return "green";
  if (s === "pending" || s === "chunking" || s === "embedding") return "amber";
  return "red";
}

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { current: service } = useService();

  const { data, isLoading } = useQuery({
    queryKey: ["document", service?.id, id],
    queryFn: () => DocumentsApi.get(service!.id, id),
    enabled: Number.isFinite(id) && service != null,
  });

  const [showPreview, setShowPreview] = useState(false);
  const [showMarkdown, setShowMarkdown] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const markdownQuery = useQuery({
    queryKey: ["document-markdown", service?.id, id],
    queryFn: () => DocumentsApi.previewText(service!.id, id),
    enabled: showMarkdown && service != null && Number.isFinite(id),
  });
  const [replaceFile, setReplaceFile] = useState<File | null>(null);
  const [replacing, setReplacing] = useState(false);

  const deleteDoc = useMutation({
    mutationFn: () => DocumentsApi.remove(service!.id, id),
    onSuccess: () => {
      toast.success("Document deleted");
      navigate("/documents");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Delete failed"),
  });

  const onReplace = async (e: FormEvent) => {
    e.preventDefault();
    if (!replaceFile) {
      toast.error("Choose a file");
      return;
    }
    setReplacing(true);
    try {
      const fd = new FormData();
      fd.set("file", replaceFile);
      await DocumentsApi.replace(service!.id, id, fd);
      setReplaceFile(null);
      void qc.invalidateQueries({ queryKey: ["document", service?.id, id] });
      toast.success("File replaced and re-indexing started");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Replace failed");
    } finally {
      setReplacing(false);
    }
  };

  if (isLoading) return <div>Loading…</div>;
  if (!data) return <div>Document not found.</div>;

  const isPdf =
    data.mime_type === "application/pdf" || data.source_filename.toLowerCase().endsWith(".pdf");
  const isText = /^text\//.test(data.mime_type);

  return (
    <div className="space-y-6">
      <ConfirmDialog
        open={confirmDelete}
        title="Delete document?"
        confirmLabel="Delete"
        onConfirm={() => {
          setConfirmDelete(false);
          deleteDoc.mutate();
        }}
        onCancel={() => setConfirmDelete(false)}
      >
        Delete <strong>{data.title}</strong>? This cannot be undone.
      </ConfirmDialog>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{data.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-[#A0AEC0]">
            <span>{data.source_filename}</span>
            <span>·</span>
            <span>{data.mime_type}</span>
            <span>·</span>
            <span>{formatBytes(data.size_bytes)}</span>
            <Badge tone={statusTone(data.status)}>{data.status}</Badge>
          </div>
          {data.description && (
            <p className="mt-2 max-w-2xl text-sm text-[#2D3748]">{data.description}</p>
          )}
          {data.error && (
            <p className="mt-2 text-sm text-red-700">Error: {data.error}</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href={service ? DocumentsApi.fileUrl(service.id, id) : "#"}
            className="inline-flex items-center justify-center rounded-md border border-gray-200 bg-white px-3 py-2 text-sm font-medium hover:bg-gray-100"
          >
            Download
          </a>
          <Button variant="secondary" size="sm" onClick={() => setShowPreview((v) => !v)}>
            {showPreview ? "Hide preview" : "Preview"}
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setShowMarkdown((v) => !v)}>
            {showMarkdown ? "Hide markdown" : "View markdown"}
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => setConfirmDelete(true)}
          >
            Delete
          </Button>
        </div>
      </div>

      {showMarkdown && (
        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#A0AEC0]">
            Converted Markdown
          </h2>
          {markdownQuery.isLoading && <div className="text-sm text-[#A0AEC0]">Loading…</div>}
          {markdownQuery.isError && (
            <div className="text-sm text-red-600">Failed to load markdown.</div>
          )}
          {markdownQuery.data && (
            <div className="prose prose-sm max-w-none overflow-auto rounded border border-gray-100 bg-gray-50 p-4 max-h-[70vh]">
              <ReactMarkdown>{markdownQuery.data.text}</ReactMarkdown>
            </div>
          )}
        </Card>
      )}

      {showPreview && (
        <Card className="overflow-hidden p-0">
          {isPdf || isText ? (
            <iframe
              title="preview"
              src={service ? DocumentsApi.fileUrl(service.id, id) : ""}
              className="h-[70vh] w-full border-0 bg-white"
            />
          ) : (
            <div className="p-4 text-sm text-[#A0AEC0]">
              No in-browser preview for this type. Use Download.
            </div>
          )}
        </Card>
      )}

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#A0AEC0]">
          Replace file
        </h2>
        <form onSubmit={onReplace} className="flex flex-wrap items-end gap-3">
          <div className="min-w-[200px] flex-1">
            <Label htmlFor="rep">New file</Label>
            <Input
              id="rep"
              type="file"
              onChange={(e) => setReplaceFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <Button type="submit" disabled={replacing}>
            {replacing ? "Replacing…" : "Replace and re-index"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
