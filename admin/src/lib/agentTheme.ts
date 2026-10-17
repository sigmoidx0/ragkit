import type { AgentAccent, AgentConfig } from "@/api/types";

export interface AgentTheme {
  icon: string;
  accent: string;
  gradientFrom: string;
  gradientTo: string;
}

export const ACCENT_THEMES: Record<AgentAccent, Omit<AgentTheme, "icon">> = {
  teal: { accent: "#14B8A6", gradientFrom: "#2DD4BF", gradientTo: "#06B6D4" },
  blue: { accent: "#3B82F6", gradientFrom: "#3B82F6", gradientTo: "#6366F1" },
  purple: { accent: "#8B5CF6", gradientFrom: "#8B5CF6", gradientTo: "#EC4899" },
  amber: { accent: "#F59E0B", gradientFrom: "#F59E0B", gradientTo: "#EF4444" },
  rose: { accent: "#F43F5E", gradientFrom: "#F43F5E", gradientTo: "#FB923C" },
  slate: { accent: "#64748B", gradientFrom: "#64748B", gradientTo: "#334155" },
};

/** Guess a theme from the agent's name — used until someone picks one. */
function themeFromName(name: string, slug = ""): AgentTheme {
  const key = `${slug} ${name}`.toLowerCase();
  if (/legal|법|law/.test(key)) return { icon: "⚖️", ...ACCENT_THEMES.blue };
  if (/medical|의|health|병원|clinic/.test(key))
    return { icon: "🏥", accent: "#10B981", gradientFrom: "#10B981", gradientTo: "#059669" };
  if (/finance|금|money|투자|bank/.test(key)) return { icon: "💰", ...ACCENT_THEMES.amber };
  if (/edu|교육|학/.test(key)) return { icon: "📚", ...ACCENT_THEMES.purple };
  return { icon: "🤖", ...ACCENT_THEMES.teal };
}

/**
 * An agent's (or workspace's) theme: the chosen icon and accent, falling back
 * to a guess from the name. Workspaces have no settings, so they always guess.
 */
export function getAgentTheme(agent: {
  name: string;
  slug?: string;
  agent_config?: Pick<AgentConfig, "icon" | "accent"> | null;
}): AgentTheme {
  const fallback = themeFromName(agent.name, agent.slug);
  const cfg = agent.agent_config;
  return {
    ...(cfg?.accent ? ACCENT_THEMES[cfg.accent] : fallback),
    icon: cfg?.icon || fallback.icon,
  };
}
