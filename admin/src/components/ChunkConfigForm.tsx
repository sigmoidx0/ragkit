import { Input, Label, Select } from "@/components/ui";
import type { ChunkConfig } from "@/api/types";

const STRATEGIES = [
  { value: "recursive", label: "Recursive (default)" },
  { value: "markdown_header", label: "Markdown Header" },
  { value: "character", label: "Character" },
  { value: "token", label: "Token (tiktoken)" },
] as const;

const HEADER_LEVELS = ["#", "##", "###", "####"];

interface Props {
  value: ChunkConfig;
  onChange: (cfg: ChunkConfig) => void;
}

export function ChunkConfigForm({ value, onChange }: Props) {
  const strategy = value.strategy;

  function setStrategy(s: ChunkConfig["strategy"]) {
    if (s === "recursive") onChange({ strategy: "recursive" });
    else if (s === "markdown_header") onChange({ strategy: "markdown_header", headers_to_split_on: ["#", "##", "###"] });
    else if (s === "character") onChange({ strategy: "character", separator: "\n\n" });
    else onChange({ strategy: "token" });
  }

  return (
    <div className="space-y-3">
      <div>
        <Label htmlFor="chunk-strategy">Chunking Strategy</Label>
        <Select
          id="chunk-strategy"
          value={strategy}
          onChange={(e) => setStrategy(e.target.value as ChunkConfig["strategy"])}
        >
          {STRATEGIES.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </Select>
      </div>

      {/* ── Recursive ─────────────────────────────────────── */}
      {strategy === "recursive" && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="cc-size">Chunk size (chars)</Label>
            <Input
              id="cc-size"
              type="number"
              min={100}
              placeholder="1000"
              value={(value as { chunk_size?: number }).chunk_size ?? ""}
              onChange={(e) => onChange({ ...value, chunk_size: e.target.value ? Number(e.target.value) : undefined })}
            />
          </div>
          <div>
            <Label htmlFor="cc-overlap">Overlap (chars)</Label>
            <Input
              id="cc-overlap"
              type="number"
              min={0}
              placeholder="150"
              value={(value as { chunk_overlap?: number }).chunk_overlap ?? ""}
              onChange={(e) => onChange({ ...value, chunk_overlap: e.target.value ? Number(e.target.value) : undefined })}
            />
          </div>
        </div>
      )}

      {/* ── Markdown Header ───────────────────────────────── */}
      {strategy === "markdown_header" && (
        <div className="space-y-3">
          <div>
            <Label>Split on headers</Label>
            <div className="mt-1 flex flex-wrap gap-3">
              {HEADER_LEVELS.map((h) => {
                const cfg = value as { headers_to_split_on?: string[] };
                const checked = (cfg.headers_to_split_on ?? ["#", "##", "###"]).includes(h);
                return (
                  <label key={h} className="flex items-center gap-1.5 text-sm text-[#2D3748]">
                    <input
                      type="checkbox"
                      checked={checked}
                      className="accent-teal-400"
                      onChange={(e) => {
                        const current = cfg.headers_to_split_on ?? ["#", "##", "###"];
                        const next = e.target.checked
                          ? [...current, h].sort((a, b) => a.length - b.length)
                          : current.filter((x) => x !== h);
                        onChange({ ...value, headers_to_split_on: next });
                      }}
                    />
                    <code className="font-mono">{h}</code>
                  </label>
                );
              })}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="cc-md-size">Max chunk size (chars, optional)</Label>
              <Input
                id="cc-md-size"
                type="number"
                min={100}
                placeholder="none"
                value={(value as { chunk_size?: number }).chunk_size ?? ""}
                onChange={(e) => onChange({ ...value, chunk_size: e.target.value ? Number(e.target.value) : undefined })}
              />
            </div>
            <div>
              <Label htmlFor="cc-md-overlap">Overlap (chars)</Label>
              <Input
                id="cc-md-overlap"
                type="number"
                min={0}
                placeholder="0"
                value={(value as { chunk_overlap?: number }).chunk_overlap ?? ""}
                onChange={(e) => onChange({ ...value, chunk_overlap: e.target.value ? Number(e.target.value) : undefined })}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Character ─────────────────────────────────────── */}
      {strategy === "character" && (
        <div className="space-y-3">
          <div>
            <Label htmlFor="cc-sep">Separator</Label>
            <Select
              id="cc-sep"
              value={(value as { separator?: string }).separator ?? "\n\n"}
              onChange={(e) => onChange({ ...value, separator: e.target.value })}
            >
              <option value="\n\n">Double newline (\n\n)</option>
              <option value="\n">Single newline (\n)</option>
              <option value=". ">Period + space (. )</option>
              <option value=" ">Space</option>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="cc-char-size">Chunk size (chars)</Label>
              <Input
                id="cc-char-size"
                type="number"
                min={100}
                placeholder="1000"
                value={(value as { chunk_size?: number }).chunk_size ?? ""}
                onChange={(e) => onChange({ ...value, chunk_size: e.target.value ? Number(e.target.value) : undefined })}
              />
            </div>
            <div>
              <Label htmlFor="cc-char-overlap">Overlap (chars)</Label>
              <Input
                id="cc-char-overlap"
                type="number"
                min={0}
                placeholder="150"
                value={(value as { chunk_overlap?: number }).chunk_overlap ?? ""}
                onChange={(e) => onChange({ ...value, chunk_overlap: e.target.value ? Number(e.target.value) : undefined })}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Token ─────────────────────────────────────────── */}
      {strategy === "token" && (
        <div className="space-y-3">
          <div>
            <Label htmlFor="cc-enc">Encoding</Label>
            <Select
              id="cc-enc"
              value={(value as { encoding_name?: string }).encoding_name ?? "cl100k_base"}
              onChange={(e) => onChange({ ...value, encoding_name: e.target.value })}
            >
              <option value="cl100k_base">cl100k_base (GPT-4 / Claude)</option>
              <option value="p50k_base">p50k_base (GPT-3)</option>
              <option value="r50k_base">r50k_base (Codex)</option>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="cc-tok-size">Chunk size (tokens)</Label>
              <Input
                id="cc-tok-size"
                type="number"
                min={50}
                placeholder="512"
                value={(value as { chunk_size?: number }).chunk_size ?? ""}
                onChange={(e) => onChange({ ...value, chunk_size: e.target.value ? Number(e.target.value) : undefined })}
              />
            </div>
            <div>
              <Label htmlFor="cc-tok-overlap">Overlap (tokens)</Label>
              <Input
                id="cc-tok-overlap"
                type="number"
                min={0}
                placeholder="50"
                value={(value as { chunk_overlap?: number }).chunk_overlap ?? ""}
                onChange={(e) => onChange({ ...value, chunk_overlap: e.target.value ? Number(e.target.value) : undefined })}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
