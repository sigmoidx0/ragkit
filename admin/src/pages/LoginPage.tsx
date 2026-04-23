import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { Button, ErrorBox, Input, Label } from "@/components/ui";

export default function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/documents";

  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (user) navigate(from, { replace: true });
  }, [user, from, navigate]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Left: brand panel */}
      <div className="hidden flex-col items-center justify-center bg-gradient-to-br from-teal-400 to-cyan-600 p-12 lg:flex lg:w-1/2">
        <div className="flex flex-col items-center gap-6 text-white">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/20 backdrop-blur-sm">
            <svg viewBox="0 0 24 24" fill="currentColor" className="h-9 w-9 text-white">
              <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
            </svg>
          </div>
          <div className="text-center">
            <h1 className="text-4xl font-bold tracking-tight">RAGKIT</h1>
            <p className="mt-2 text-sm font-medium opacity-80">Admin Dashboard</p>
          </div>
          <p className="max-w-xs text-center text-sm leading-relaxed opacity-70">
            Manage your documents, services, and team members from a single place.
          </p>
        </div>
      </div>

      {/* Right: form panel */}
      <div className="flex flex-1 flex-col items-center justify-center bg-[#F8F9FA] p-8">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-400">
              <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4 text-white">
                <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
              </svg>
            </div>
            <span className="text-sm font-bold text-[#2D3748]">RAGKIT ADMIN</span>
          </div>

          <h2 className="text-2xl font-bold text-[#2D3748]">Welcome back</h2>
          <p className="mt-1 mb-8 text-sm text-[#A0AEC0]">Sign in to your admin account</p>

          <form onSubmit={onSubmit} className="space-y-5">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <ErrorBox message={error} />
            <Button type="submit" className="w-full py-2.5" disabled={submitting}>
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
