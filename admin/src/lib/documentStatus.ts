import type { DocumentStatus } from "@/api/types";

export function statusTone(s: DocumentStatus): "green" | "amber" | "red" {
  if (s === "indexed") return "green";
  if (s === "pending" || s === "chunking" || s === "embedding") return "amber";
  return "red";
}
