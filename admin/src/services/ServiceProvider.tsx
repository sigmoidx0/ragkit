import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ServicesApi } from "@/api/endpoints";
import type { ServiceWithRole } from "@/api/types";

const STORAGE_KEY = "ragkit.service_id";

interface ServiceContextValue {
  services: ServiceWithRole[];
  current: ServiceWithRole | null;
  loading: boolean;
  select: (service: ServiceWithRole) => void;
  refresh: () => Promise<void>;
}

const ServiceContext = createContext<ServiceContextValue | null>(null);

export function ServiceProvider({ children }: { children: ReactNode }) {
  const [services, setServices] = useState<ServiceWithRole[]>([]);
  const [current, setCurrent] = useState<ServiceWithRole | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const list = await ServicesApi.listMine();
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

  const select = useCallback((service: ServiceWithRole) => {
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
