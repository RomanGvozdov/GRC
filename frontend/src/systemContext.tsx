import { createContext, useContext, useState, type ReactNode } from "react";

interface SystemContextState {
  systemId: number | null; // null = вся організація
  setSystemId: (id: number | null) => void;
}

const SystemContext = createContext<SystemContextState>({
  systemId: null,
  setSystemId: () => {},
});

export function SystemProvider({ children }: { children: ReactNode }) {
  const [systemId, setSystemIdState] = useState<number | null>(() => {
    const stored = localStorage.getItem("system_id");
    return stored ? Number(stored) : null;
  });

  const setSystemId = (id: number | null) => {
    setSystemIdState(id);
    if (id) localStorage.setItem("system_id", String(id));
    else localStorage.removeItem("system_id");
  };

  return (
    <SystemContext.Provider value={{ systemId, setSystemId }}>{children}</SystemContext.Provider>
  );
}

export function useSystem() {
  return useContext(SystemContext);
}

/** Додає system_id до query-рядка, якщо обрано конкретну ІКС. */
export function withSystem(url: string, systemId: number | null): string {
  if (!systemId) return url;
  return url + (url.includes("?") ? "&" : "?") + `system_id=${systemId}`;
}
