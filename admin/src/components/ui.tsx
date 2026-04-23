import { forwardRef } from "react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

const BTN_VARIANT: Record<ButtonVariant, string> = {
  primary:
    "bg-teal-400 text-white hover:bg-teal-500 disabled:bg-teal-200",
  secondary:
    "bg-white text-[#2D3748] border border-gray-200 hover:bg-gray-50 shadow-sm disabled:text-gray-400",
  ghost: "bg-transparent hover:bg-gray-100 text-[#2D3748]",
  danger: "bg-red-500 text-white hover:bg-red-600 disabled:bg-red-300",
};

const BTN_SIZE: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs rounded-xl",
  md: "px-4 py-2 text-sm rounded-xl",
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize }
>(function Button({ variant = "primary", size = "md", className, ...rest }, ref) {
  return (
    <button
      ref={ref}
      {...rest}
      className={cn(
        "inline-flex items-center justify-center font-semibold transition-colors disabled:cursor-not-allowed",
        BTN_VARIANT[variant],
        BTN_SIZE[size],
        className,
      )}
    />
  );
});

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...rest}
      className={cn(
        "block w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-[#2D3748] placeholder:text-[#A0AEC0] shadow-sm focus:border-teal-300 focus:outline-none focus:ring-2 focus:ring-teal-100 disabled:bg-gray-50",
        className,
      )}
    />
  );
}

export function Textarea({
  className,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...rest}
      className={cn(
        "block w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-[#2D3748] placeholder:text-[#A0AEC0] shadow-sm focus:border-teal-300 focus:outline-none focus:ring-2 focus:ring-teal-100",
        className,
      )}
    />
  );
}

export function Select({
  className,
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...rest}
      className={cn(
        "block w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-[#2D3748] shadow-sm focus:border-teal-300 focus:outline-none focus:ring-2 focus:ring-teal-100",
        className,
      )}
    >
      {children}
    </select>
  );
}

export function Label({
  children,
  htmlFor,
  className,
}: {
  children: ReactNode;
  htmlFor?: string;
  className?: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className={cn("mb-1 block text-xs font-semibold text-[#2D3748]", className)}
    >
      {children}
    </label>
  );
}

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-gray-100 bg-white shadow-md",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Badge({
  children,
  tone = "slate",
}: {
  children: ReactNode;
  tone?: "slate" | "green" | "red" | "amber" | "blue";
}) {
  const tones: Record<string, string> = {
    slate: "bg-gray-100 text-gray-600",
    green: "bg-teal-50 text-teal-700",
    red: "bg-red-50 text-red-600",
    amber: "bg-amber-50 text-amber-700",
    blue: "bg-blue-50 text-blue-700",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-lg px-2 py-0.5 text-xs font-semibold",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

export function ErrorBox({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="rounded-xl border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-600">
      {message}
    </div>
  );
}

export function formatBytes(n: number): string {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}
