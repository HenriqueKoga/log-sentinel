import { createContext } from "react";
import type { TokenPair } from "../../shared/auth/storage";

export type AuthContextValue = {
  isAuthenticated: boolean;
  accessToken: string | null;
  setTokenPair: (pair: TokenPair) => void;
  logout: () => void;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

