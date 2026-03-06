import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  List,
  ListItem,
  ListItemText,
  TextField,
  Typography,
} from "@mui/material";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getErrorMessage } from "../../shared/api/errors";
import { CopyButton } from "../../shared/components/CopyButton";
import { ErrorState, LoadingState } from "../../shared/components/States";
import { formatDateTime } from "../../shared/utils/format";
import { useCreateToken, useProjectTokens, useRevokeToken } from "./api";
import { useState } from "react";

export function ProjectTokensPage() {
  const { t } = useTranslation();
  const projectId = Number(useParams().projectId);
  const tokens = useProjectTokens(projectId);
  const create = useCreateToken(projectId);
  const revoke = useRevokeToken(projectId);

  const [createdToken, setCreatedToken] = useState<string | null>(null);
  const [tokenName, setTokenName] = useState<string>("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
        <Typography variant="h5">{t("tokens.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Button
          variant="contained"
          disabled={create.isPending || !Number.isFinite(projectId)}
          onClick={() => setIsDialogOpen(true)}
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
          <List dense>
            {tokens.data.map((tok) => (
              <Box key={tok.id}>
                <ListItem
                  secondaryAction={
                    <Button
                      size="small"
                      color="warning"
                      disabled={revoke.isPending || !!tok.revoked_at}
                      onClick={async () => revoke.mutateAsync(tok.id)}
                    >
                      {t("tokens.revoke")}
                    </Button>
                  }
                >
                  <ListItemText
                    primary={
                      tok.name
                        ? `${tok.name} — ${tok.revoked_at ? t("tokens.revoked") : t("tokens.active")}`
                        : `${t("tokens.tokenId")} #${tok.id} — ${
                            tok.revoked_at ? t("tokens.revoked") : t("tokens.active")
                          }`
                    }
                    secondary={
                      <>
                        {t("tokens.lastUsed")}: {formatDateTime(tok.last_used_at)}
                        {" • "}
                        {t("tokens.revokedAt")}: {formatDateTime(tok.revoked_at)}
                      </>
                    }
                  />
                </ListItem>
                <Divider />
              </Box>
            ))}
            {tokens.data.length === 0 && (
              <Typography sx={{ mt: 2 }} color="text.secondary">
                {t("tokens.empty")}
              </Typography>
            )}
          </List>
        </>
      )}

      {(create.error || revoke.error) && (
        <ErrorState message={getErrorMessage(create.error ?? revoke.error)} />
      )}

      <Dialog
        open={isDialogOpen}
        onClose={() => {
          if (!create.isPending) setIsDialogOpen(false);
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
                setIsDialogOpen(false);
                setTokenName("");
              }
            }}
          >
            {t("common.cancel")}
          </Button>
          <Button
            variant="contained"
            disabled={create.isPending || !Number.isFinite(projectId)}
            onClick={async () => {
              const tok = await create.mutateAsync({ name: tokenName || null });
              if (tok.token && tok.token !== "hidden") setCreatedToken(tok.token);
              setTokenName("");
              setIsDialogOpen(false);
            }}
          >
            {t("tokens.create")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

