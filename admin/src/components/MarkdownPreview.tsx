import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownPreviewProps {
  markdown?: string;
  isLoading?: boolean;
  isError?: boolean;
  fileName?: string;
  contentClassName?: string;
}

export function MarkdownPreview({
  markdown,
  isLoading = false,
  isError = false,
  fileName,
  contentClassName = "min-h-0 flex-1 overflow-y-auto",
}: MarkdownPreviewProps) {
  const [raw, setRaw] = useState(false);

  if (isLoading || isError || !markdown) {
    return (
      <div className="flex flex-1 items-center justify-center py-10 text-sm">
        {isError ? (
          <span className="text-red-400">Failed to convert file.</span>
        ) : (
          <span className="text-[#A0AEC0]">
            {isLoading
              ? `Converting ${fileName ?? "file"}…`
              : "Select a file to preview its content"}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 justify-end border-b border-gray-100 px-4 py-2 dark:border-gray-700">
        <div className="flex rounded-md border border-gray-200 text-xs font-medium dark:border-gray-600">
          <button
            className={`rounded-l-md px-3 py-1 transition-colors ${
              !raw
                ? "bg-gray-100 text-gray-900 dark:bg-gray-600 dark:text-gray-100"
                : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            }`}
            onClick={() => setRaw(false)}
          >
            Preview
          </button>
          <button
            className={`rounded-r-md border-l border-gray-200 px-3 py-1 transition-colors dark:border-gray-600 ${
              raw
                ? "bg-gray-100 text-gray-900 dark:bg-gray-600 dark:text-gray-100"
                : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            }`}
            onClick={() => setRaw(true)}
          >
            Raw
          </button>
        </div>
      </div>
      <div className={contentClassName}>
        {raw ? (
          <pre className="p-4 text-xs leading-relaxed whitespace-pre-wrap break-words text-gray-800 dark:text-gray-200">
            {markdown}
          </pre>
        ) : (
          <div className="prose prose-sm max-w-none p-4 dark:prose-invert">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
