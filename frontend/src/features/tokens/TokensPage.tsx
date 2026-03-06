import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useCreateToken, useProjectTokens, useProjects } from "../projects/api";
import { CopyButton } from "../../shared/components/CopyButton";
import { ErrorState, LoadingState } from "../../shared/components/States";
import { getErrorMessage } from "../../shared/api/errors";
import { formatDateTime } from "../../shared/utils/format";

export function TokensPage() {
  const { t } = useTranslation();
  const projectsQuery = useProjects();

  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [createdToken, setCreatedToken] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [tokenName, setTokenName] = useState("");

  useEffect(() => {
    if (!projectsQuery.data || projectsQuery.data.length === 0) return;
    if (selectedProjectId === null) {
      setSelectedProjectId(projectsQuery.data[0].id);
    }
  }, [projectsQuery.data, selectedProjectId]);

  const selectedProject = useMemo(
    () => projectsQuery.data?.find((p) => p.id === selectedProjectId) ?? null,
    [projectsQuery.data, selectedProjectId],
  );

  const projectId = selectedProjectId ?? 0;
  const tokens = useProjectTokens(projectId);
  const create = useCreateToken(projectId);

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
        <Typography variant="h5">{t("tokens.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
        {projectsQuery.isLoading && <LoadingState label={t("common.loading")} />}
        {projectsQuery.data && projectsQuery.data.length > 0 && (
          <FormControl size="small" sx={{ minWidth: 220 }}>
            <InputLabel id="tokens-project-select-label">{t("projects.title")}</InputLabel>
            <Select
              labelId="tokens-project-select-label"
              label={t("projects.title")}
              value={selectedProjectId ?? ""}
              onChange={(e) => setSelectedProjectId(Number(e.target.value))}
            >
              {projectsQuery.data.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
        <Button
          variant="contained"
          disabled={!selectedProject || create.isPending}
          onClick={() => setDialogOpen(true)}
        >
          {t("tokens.create")}
        </Button>
      </Box>

      {createdToken && (
        <Alert
          severity="success"
          sx={{ mb: 2 }}
          action={<CopyButton value={createdToken} />}
          onClose={() => setCreatedToken(null)}
        >
          <strong>{t("tokens.newToken")}</strong> {createdToken}
        </Alert>
      )}

      {tokens.isLoading && <LoadingState label={t("common.loading")} />}
      {tokens.error && <ErrorState message={getErrorMessage(tokens.error)} />}

      {tokens.data && (
        <>
          <Typography color="text.secondary" sx={{ mb: 1 }}>
            {t("tokens.note")}
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("projects.name")}</TableCell>
                <TableCell>{t("tokens.tokenId")}</TableCell>
                <TableCell>{t("tokens.lastUsed")}</TableCell>
                <TableCell>{t("tokens.revokedAt")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {tokens.data.map((tok) => (
                <TableRow key={tok.id}>
                  <TableCell>{selectedProject?.name ?? "—"}</TableCell>
                  <TableCell>{tok.name || `#${tok.id}`}</TableCell>
                  <TableCell>{formatDateTime(tok.last_used_at)}</TableCell>
                  <TableCell>{formatDateTime(tok.revoked_at)}</TableCell>
                </TableRow>
              ))}
              {tokens.data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4}>
                    <Typography sx={{ mt: 2 }} color="text.secondary">
                      {t("tokens.empty")}
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </>
      )}

      {(projectsQuery.error || create.error) && (
        <ErrorState message={getErrorMessage(projectsQuery.error ?? create.error)} />
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => {
          if (!create.isPending) {
            setDialogOpen(false);
            setTokenName("");
          }
        }}
      >
        <DialogTitle>{t("tokens.createTitle")}</DialogTitle>
        <DialogContent>
          <TextField
            margin="dense"
            fullWidth
            label={t("tokens.name")}
            value={tokenName}
            onChange={(e) => setTokenName(e.target.value)}
            autoFocus
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              if (!create.isPending) {
                setDialogOpen(false);
                setTokenName("");
              }
            }}
          >
            {t("common.cancel")}
          </Button>
          <Button
            variant="contained"
            disabled={!selectedProject || create.isPending}
            onClick={async () => {
              const tok = await create.mutateAsync({ name: tokenName || null });
              if (tok.token && tok.token !== "hidden") setCreatedToken(tok.token);
              setTokenName("");
              setDialogOpen(false);
            }}
          >
            {t("tokens.create")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

