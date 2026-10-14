import ReactMarkdown from "react-markdown";
import { useNavigate } from "react-router-dom";
import remarkGfm from "remark-gfm";

import type { SourceItem } from "@/api/types";

// "[3]" not already part of a markdown link ("[3](...)").
const CITATION = /\[(\d{1,2})\](?!\()/g;
const CITE_PREFIX = "#cite-";

/**
 * Chunks are stored as the markdown the converter produced, so a raw snippet
 * carries image tags and link syntax. Reduce it to readable text for the card.
 */
function plainSnippet(text: string): string {
  return text
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "") // images
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1") // links → their text
    .replace(/[*_`#>|]+/g, " ") // emphasis, headings, quotes, table pipes
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Markdown answer whose [N] markers become citation chips: hover for the
 * passage the claim came from, click to open the document.
 *
 * Markers are rewritten into links before parsing so the markdown parser,
 * not a regex over rendered text, decides where they sit.
 */
export function CitedMarkdown({ content, sources }: { content: string; sources: SourceItem[] }) {
  const navigate = useNavigate();
  // The first search (the seeded one) is what most citations refer to, so the
  // first source carrying an index wins when later searches reuse it.
  const byIndex = new Map<number, SourceItem>();
  for (const s of sources) if (!byIndex.has(s.index)) byIndex.set(s.index, s);

  const linked = content.replace(CITATION, (match, n) =>
    byIndex.has(Number(n)) ? `[${n}](${CITE_PREFIX}${n})` : match,
  );

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children }) => {
          const source = href?.startsWith(CITE_PREFIX) ? byIndex.get(Number(href.slice(CITE_PREFIX.length))) : null;
          if (!source) {
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          }
          return <CitationChip source={source} onOpen={() => navigate(`/documents/${source.document_id}`)} />;
        },
      }}
    >
      {linked}
    </ReactMarkdown>
  );
}

function CitationChip({ source, onOpen }: { source: SourceItem; onOpen: () => void }) {
  return (
    <span className="group relative inline-block align-baseline">
      <button
        type="button"
        onClick={onOpen}
        className="mx-0.5 rounded-md bg-teal-50 px-1 font-mono text-[10px] font-semibold text-teal-700 no-underline transition-colors hover:bg-teal-100 dark:bg-teal-900/40 dark:text-teal-300"
      >
        {source.index}
      </button>
      {/* Hover card — pure CSS so it costs nothing per chip until shown */}
      <span className="pointer-events-none invisible absolute bottom-full left-1/2 z-30 mb-2 w-72 -translate-x-1/2 rounded-xl border border-gray-200 bg-white p-3 text-left opacity-0 shadow-xl transition-opacity group-hover:visible group-hover:opacity-100 dark:border-gray-600 dark:bg-gray-800">
        <span className="flex items-center justify-between gap-2">
          <span className="truncate text-xs font-semibold text-gray-800 dark:text-gray-100">
            {source.title ?? `Document #${source.document_id}`}
          </span>
          <span className="shrink-0 font-mono text-[10px] text-gray-400">
            {source.score < 0.01 ? source.score.toExponential(1) : source.score.toFixed(3)}
          </span>
        </span>
        <span className="mt-1.5 line-clamp-6 block text-[11px] font-normal leading-relaxed text-gray-600 dark:text-gray-300">
          {plainSnippet(source.snippet)}
        </span>
        <span className="mt-2 block text-[10px] text-teal-600 dark:text-teal-400">Click to open the document →</span>
      </span>
    </span>
  );
}
