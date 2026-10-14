import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AgentsApi } from "@/api/endpoints";
import type { AgentCard } from "@/api/types";

const STORAGE_KEY = "ragkit.service_id";

interface ServiceContextValue {
  services: AgentCard[];
  current: AgentCard | null;
  loading: boolean;
  select: (service: AgentCard) => void;
  refresh: () => Promise<void>;
}

const ServiceContext = createContext<ServiceContextValue | null>(null);

export function ServiceProvider({ children }: { children: ReactNode }) {
  const [services, setServices] = useState<AgentCard[]>([]);
  const [current, setCurrent] = useState<AgentCard | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      // Agent cards are a superset of the plain service list, so every page that
      // only needs id/name/role keeps working.
      const list = await AgentsApi.listMine();
      setServices(list);

      const savedId = localStorage.getItem(STORAGE_KEY);
      const saved = savedId ? list.find((s) => s.id === Number(savedId)) : null;
      setCurrent(saved ?? list[0] ?? null);
    } catch {
      setServices([]);
      setCurrent(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const select = useCallback((service: AgentCard) => {
    setCurrent(service);
    localStorage.setItem(STORAGE_KEY, String(service.id));
  }, []);

  const value = useMemo(
    () => ({ services, current, loading, select, refresh }),
    [services, current, loading, select, refresh],
  );

  return <ServiceContext.Provider value={value}>{children}</ServiceContext.Provider>;
}

export function useService(): ServiceContextValue {
  const ctx = useContext(ServiceContext);
  if (!ctx) throw new Error("useService must be used within ServiceProvider");
  return ctx;
}
