import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import * as api from "@/lib/api";
import type { Operator } from "@/types/auth";

type AuthStatus = "loading" | "authed" | "anon";

interface AuthValue {
  operator: Operator | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<Operator>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [operator, setOperator] = useState<Operator | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let active = true;
    void api
      .getMe()
      .then((next) => {
        if (!active) return;
        setOperator(next);
        setStatus("authed");
      })
      .catch(() => {
        if (!active) return;
        setOperator(null);
        setStatus("anon");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    api.setUnauthorizedHandler(() => {
      setOperator(null);
      setStatus("anon");
      toast("Session expired — please sign in again");
    });
    return () => api.setUnauthorizedHandler(null);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      operator,
      status,
      async login(email, password) {
        const next = await api.login(email, password);
        setOperator(next);
        setStatus("authed");
        return next;
      },
      async logout() {
        try {
          await api.logout();
        } catch {
          // Local sign-out still completes when the API cannot be reached.
        }
        setOperator(null);
        setStatus("anon");
        navigate("/login", { replace: true });
      },
    }),
    [navigate, operator, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
