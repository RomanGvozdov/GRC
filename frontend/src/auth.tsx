import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, hasTokens, setTokens, type User } from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  reload: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  reload: async () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!hasTokens()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const { data } = await api.get<User>("/auth/me");
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const logout = useCallback(() => {
    setTokens(null, null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, reload, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

const LEVEL_RANK: Record<string, number> = { none: 0, read: 1, write: 2, manage: 3 };

export function hasPermission(user: User | null, module: string, level: string): boolean {
  const granted = user?.permissions?.[module] ?? "none";
  return (LEVEL_RANK[granted] ?? 0) >= (LEVEL_RANK[level] ?? 0);
}

export function canManage(user: User | null, module: string): boolean {
  return hasPermission(user, module, "manage");
}

export function canEdit(user: User | null, module: string): boolean {
  return hasPermission(user, module, "write");
}
