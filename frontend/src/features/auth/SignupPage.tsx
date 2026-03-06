import { useState } from "react";
import { Box, Button, Paper, TextField, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../app/providers/useAuth";
import { getAuthErrorMessage } from "./authErrors";

const API_BASE_URL = import.meta.env.DEV
  ? ""
  : ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "");

export const SignupPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const auth = useAuth();

  const [tenantName, setTenantName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/signup`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          tenant_name: tenantName,
          email,
          password,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(getAuthErrorMessage(response, data ?? {}, t));
        return;
      }

      const data = (await response.json()) as {
        access_token: string;
        refresh_token: string;
        token_type: string;
      };
      auth.setTokenPair({ accessToken: data.access_token, refreshToken: data.refresh_token });
      navigate("/");
    } catch {
      setError(t("auth.errorNetwork"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 px-4 py-6">
      <div className="relative w-full max-w-[480px]">
        <img
          src="/logo.png"
          alt="LogSentinel"
          style={{ height: 300, maxWidth: 520 }}
          className="absolute left-1/2 -top-40 w-auto -translate-x-1/2 object-contain drop-shadow-2xl"
        />
        <Box
          sx={{
            width: "100%",
            maxWidth: 420,
            mx: "auto",
          }}
        >
          <Paper
            sx={{
              mt: 12,
              p: 4,
              width: "100%",
              bgcolor: "rgba(15,23,42,0.96)",
              borderRadius: 3,
              border: "1px solid rgba(148,163,184,0.35)",
              boxShadow: "0 24px 80px rgba(15,23,42,0.9)",
              backdropFilter: "blur(18px)",
            }}
          >
            <Typography variant="h6" gutterBottom sx={{ color: "rgb(226,232,240)" }}>
              {t("auth.signup")}
            </Typography>
            <Typography variant="body2" sx={{ mb: 2, color: "rgba(148,163,184,0.9)" }}>
              Crie uma conta para começar a monitorar seus logs.
            </Typography>
            <Box component="form" onSubmit={handleSubmit}>
              <TextField
                fullWidth
                margin="normal"
                label={t("auth.tenantName")}
                name="tenantName"
                value={tenantName}
                onChange={(e) => setTenantName(e.target.value)}
              />
              <TextField
                fullWidth
                margin="normal"
                label={t("auth.email")}
                type="email"
                name="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <TextField
                fullWidth
                margin="normal"
                label={t("auth.password")}
                type="password"
                name="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              {error && (
                <Typography color="error" variant="body2" sx={{ mt: 1 }}>
                  {error}
                </Typography>
              )}
              <Button
                fullWidth
                type="submit"
                variant="contained"
                sx={{ mt: 2, borderRadius: 9999 }}
                disabled={submitting}
              >
                {t("auth.submit")}
              </Button>
              <Button
                fullWidth
                variant="outlined"
                sx={{ mt: 1, borderRadius: 9999, borderColor: "rgba(148,163,184,0.6)", color: "rgba(148,163,184,0.9)" }}
                onClick={() => navigate("/login")}
              >
                {t("auth.backToLogin")}
              </Button>
            </Box>
          </Paper>
        </Box>
      </div>
    </div>
  );
};

