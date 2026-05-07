import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { DocumentsApi } from "@/api/endpoints";
import { Badge, Button, Card, CardHeader, FormField, Input, SectionHeading, Textarea, formatBytes } from "@/components/ui";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { MarkdownPreview } from "@/components/MarkdownPreview";
import { useService } from "@/services/ServiceProvider";
import { statusTone } from "@/lib/documentStatus";

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
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);

  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");

  useEffect(() => {
    if (data) {
      setEditTitle(data.title);
      setEditDescription(data.description ?? "");
    }
  }, [data]);

  useEffect(() => {
    if (!showPreview || !service) return;
    let cancelled = false;
    void DocumentsApi.fetchFile(service.id, id).then(({ blob }) => {
      if (cancelled) return;
      setPreviewBlobUrl(URL.createObjectURL(blob));
    });
    return () => {
      cancelled = true;
      setPreviewBlobUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    };
  }, [showPreview, service?.id, id]);

  const handleDownload = async () => {
    if (!service) return;
    const { blob, filename } = await DocumentsApi.fetchFile(service.id, id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename ?? data?.source_filename ?? "";
    a.click();
    URL.revokeObjectURL(url);
  };

  const markdownQuery = useQuery({
    queryKey: ["document-markdown", service?.id, id],
    queryFn: () => DocumentsApi.previewText(service!.id, id),
    enabled: showMarkdown && service != null && Number.isFinite(id),
  });

  const deleteDoc = useMutation({
    mutationFn: () => DocumentsApi.remove(service!.id, id),
    onSuccess: () => {
      toast.success("Document deleted");
      navigate("/documents");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Delete failed"),
  });

  const updateMeta = useMutation({
    mutationFn: () =>
      DocumentsApi.update(service!.id, id, {
        title: editTitle || undefined,
        description: editDescription || undefined,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["document", service?.id, id] });
      toast.success("Saved");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Save failed"),
  });

  if (isLoading) return <div>Loading…</div>;
  if (!data) return <div>Document not found.</div>;

  const isPdf =
    data.mime_type === "application/pdf" || data.source_filename.toLowerCase().endsWith(".pdf");
  const isText = /^text\//.test(data.mime_type);

  const metaDirty =
    editTitle !== data.title || editDescription !== (data.description ?? "");

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
            <span>·</span>
            <span>{data.embedding_model ?? "—"}</span>
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
          <Button variant="secondary" size="sm" onClick={() => void handleDownload()}>
            Download
          </Button>
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
        <Card className="overflow-hidden p-0">
          <CardHeader>
            <SectionHeading>Converted Markdown</SectionHeading>
          </CardHeader>
          <MarkdownPreview
            markdown={markdownQuery.data?.text}
            isLoading={markdownQuery.isLoading}
            isError={markdownQuery.isError}
            contentClassName="max-h-[70vh] overflow-auto"
          />
        </Card>
      )}

      {showPreview && (
        <Card className="overflow-hidden p-0">
          {isPdf || isText ? (
            <iframe
              title="preview"
              src={previewBlobUrl ?? ""}
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
        <SectionHeading className="mb-3">Edit metadata</SectionHeading>
        <div className="space-y-3">
          <FormField label="Title" htmlFor="meta-title">
            <Input
              id="meta-title"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
            />
          </FormField>
          <FormField label="Description" htmlFor="meta-desc">
            <Textarea
              id="meta-desc"
              rows={3}
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
            />
          </FormField>
          <Button
            disabled={!metaDirty || updateMeta.isPending}
            onClick={() => updateMeta.mutate()}
          >
            {updateMeta.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
