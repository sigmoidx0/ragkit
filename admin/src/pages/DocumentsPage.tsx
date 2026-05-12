import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { DocumentsApi, IngestApi } from "@/api/endpoints";
import { Badge, Button, Card, CardHeader, ConfigSection, FormField, Input, SectionHeading, Textarea } from "@/components/ui";
import { DataTable, type Column } from "@/components/DataTable";
import { ChunkConfigForm } from "@/components/ChunkConfigForm";
import { MarkdownPreview } from "@/components/MarkdownPreview";
import { useService } from "@/services/ServiceProvider";
import { statusTone } from "@/lib/documentStatus";
import type { ChunkConfig, ChunkPreviewResponse, DocumentSummary } from "@/api/types";

const DOC_COLUMNS: Column<DocumentSummary>[] = [
  {
    header: "Title",
    render: (d) => (
      <div>
        <Link to={`/documents/${d.id}`} className="font-medium text-[#2D3748] hover:underline dark:text-gray-100">
          {d.title}
        </Link>
        {d.description && (
          <div className="line-clamp-1 text-xs text-[#A0AEC0]">{d.description}</div>
        )}
      </div>
    ),
  },
  { header: "File", render: (d) => <span className="text-[#A0AEC0]">{d.source_filename}</span> },
  { header: "Status", render: (d) => <Badge tone={statusTone(d.status)}>{d.status}</Badge> },
  {
    header: "Embedding Model",
    render: (d) => (
      <span className="text-[#A0AEC0]">{d.embedding_model ?? "—"}</span>
    ),
  },
  {
    header: "Created",
    render: (d) => (
      <span className="text-[#A0AEC0]">{new Date(d.created_at).toLocaleString()}</span>
    ),
  },
];


export default function DocumentsPage() {
  const qc = useQueryClient();
  const { current: service } = useService();
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 25;

  const listQuery = useQuery({
    queryKey: ["documents", service?.id, { q, limit, offset }],
    queryFn: () => DocumentsApi.list(service!.id, { q: q || undefined, limit, offset }),
    enabled: service != null,
  });

  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [chunkConfig, setChunkConfig] = useState<ChunkConfig>({ strategy: "recursive" });

  const previewMutation = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData();
      fd.set("file", f);
      return IngestApi.previewChunks(fd);
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    if (selected?.type === "application/pdf" || selected?.name.toLowerCase().endsWith(".pdf")) {
      toast.error("PDF files are not supported. Please upload a different format.");
      e.target.value = "";
      return;
    }
    setFile(selected);
    if (selected) {
      previewMutation.mutate(selected);
    } else {
      previewMutation.reset();
    }
  };

  const createDoc = useMutation({
    mutationFn: (fd: FormData) => DocumentsApi.create(service!.id, fd),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["documents", service?.id] });
      setFile(null);
      setTitle("");
      setDescription("");
      setChunkConfig({ strategy: "recursive" });
      previewMutation.reset();
      toast.success("Document uploaded successfully");
    },
  });

  const onUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!service) {
      toast.error("No service selected");
      return;
    }
    if (!file) {
      toast.error("Please choose a file");
      return;
    }
    if (!title.trim()) {
      toast.error("Title is required");
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.set("file", file);
      fd.set("title", title);
      if (description) fd.set("description", description);
      fd.set("chunk_config", JSON.stringify(chunkConfig));
      await createDoc.mutateAsync(fd);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;

  const previewData = previewMutation.data as ChunkPreviewResponse | undefined;
  const previewProps = {
    markdown: previewData?.markdown,
    isLoading: previewMutation.isPending,
    isError: previewMutation.isError,
    fileName: file?.name,
  };

  if (!service) {
    return <div className="text-[#A0AEC0]">No service available.</div>;
  }

  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_0.6fr] lg:gap-6">
      <div className="space-y-6 lg:self-start">
        <Card className="p-5">
          <div className="mb-3 flex items-center justify-between">
            <SectionHeading>Upload</SectionHeading>
            <span className="text-xs text-[#A0AEC0]">{total} total</span>
          </div>
          <form onSubmit={onUpload} className="grid gap-4 md:grid-cols-2">
            <FormField label="Title" htmlFor="title">
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </FormField>
            <FormField label="File" htmlFor="file">
              <Input id="file" type="file" accept=".txt,.md,.markdown,.rst,.docx,.pptx,.xlsx,.xls" onChange={handleFileChange} required />
            </FormField>
            <FormField label="Description (optional)" htmlFor="description" className="md:col-span-2">
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
              />
            </FormField>
            <ConfigSection className="md:col-span-2">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-[#A0AEC0]">
                Chunking Strategy
              </p>
              <ChunkConfigForm value={chunkConfig} onChange={setChunkConfig} />
            </ConfigSection>
            <div className="md:col-span-2">
              <Button type="submit" disabled={uploading}>
                {uploading ? "Uploading…" : "Upload"}
              </Button>
            </div>
          </form>
        </Card>

        {/* Mobile-only preview: shown between upload form and list */}
        {(file || previewMutation.isPending) && (
          <Card className="overflow-hidden lg:hidden">
            <CardHeader>
              <SectionHeading>Preview</SectionHeading>
            </CardHeader>
            <MarkdownPreview {...previewProps} contentClassName="max-h-72 overflow-y-auto" />
          </Card>
        )}

        <Card>
          <div className="flex items-center justify-between gap-3 border-b border-gray-100 p-4 dark:border-gray-700">
            <Input
              placeholder="Filter by title…"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setOffset(0);
              }}
              className="max-w-sm"
            />
            <div className="flex items-center gap-2 text-sm text-[#A0AEC0]">
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
          <DataTable<DocumentSummary>
            columns={DOC_COLUMNS}
            rows={items}
            rowKey={(d) => d.id}
            isLoading={listQuery.isLoading}
            emptyMessage="No documents yet."
          />
        </Card>
      </div>

      <div className="hidden lg:flex lg:flex-col lg:overflow-hidden">
        <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <CardHeader className="shrink-0">
              <SectionHeading>Preview</SectionHeading>
            </CardHeader>
            <MarkdownPreview {...previewProps} />
        </Card>
      </div>
    </div>
  );
}
