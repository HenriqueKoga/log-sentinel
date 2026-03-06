import { Alert, Box, CircularProgress } from "@mui/material";

export function LoadingState({ label }: { label?: string }) {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 2, py: 4 }}>
      <CircularProgress size={22} />
      <span>{label ?? "Loading..."}</span>
    </Box>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <Alert severity="error" sx={{ my: 2 }}>
      {message}
    </Alert>
  );
}

