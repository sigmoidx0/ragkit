import { useEffect, useRef, type ReactNode } from "react";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";

interface ConfirmDialogProps {
  open: boolean;
  title?: string;
  children: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title = "Are you sure?",
  children,
  confirmLabel = "Confirm",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) cancelRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onCancel}
        aria-hidden
      />
      <div
        className={cn(
          "relative z-10 mx-4 w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl",
        )}
        role="dialog"
        aria-modal
        aria-labelledby="confirm-title"
      >
        <h2 id="confirm-title" className="mb-2 text-base font-semibold text-[#2D3748]">
          {title}
        </h2>
        <p className="mb-6 text-sm text-[#A0AEC0]">{children}</p>
        <div className="flex justify-end gap-2">
          <Button ref={cancelRef} variant="secondary" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="danger" size="sm" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
