import { PropsWithChildren, useCallback, useMemo, useState } from "react";
import { clearTokens, getAccessToken, setTokens, TokenPair } from "../../shared/auth/storage";
import { AuthContext, type AuthContextValue } from "./authContext";

export function AuthProvider({ children }: PropsWithChildren) {
  const [accessToken, setAccessToken] = useState<string | null>(() => getAccessToken());

  const setTokenPair = useCallback((pair: TokenPair) => {
    setTokens(pair);
    setAccessToken(pair.accessToken);
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setAccessToken(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: !!accessToken,
      accessToken,
      setTokenPair,
      logout,
    }),
    [accessToken, logout, setTokenPair],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

