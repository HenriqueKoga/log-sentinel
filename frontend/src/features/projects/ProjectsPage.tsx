import { useState } from "react";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  List,
  ListItemButton,
  ListItemText,
  TextField,
  Typography,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getErrorMessage } from "../../shared/api/errors";
import { ErrorState, LoadingState } from "../../shared/components/States";
import { formatDateTime } from "../../shared/utils/format";
import { useCreateProject, useProjects } from "./api";

export function ProjectsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const projects = useProjects();
  const create = useCreateProject();

  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
        <Typography variant="h5">{t("projects.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="contained" onClick={() => setOpen(true)} sx={{ cursor: "pointer" }}>
          {t("projects.create")}
        </Button>
      </Box>

      {projects.isLoading && <LoadingState label={t("common.loading")} />}
      {projects.error && <ErrorState message={getErrorMessage(projects.error)} />}
      {projects.data && (
        <List dense>
          {projects.data.map((p) => (
            <ListItemButton key={p.id} onClick={() => navigate(`/projects/${p.id}/tokens`)}>
              <ListItemText primary={p.name} secondary={`${t("common.createdAt")}: ${formatDateTime(p.created_at)}`} />
            </ListItemButton>
          ))}
          {projects.data.length === 0 && (
            <Typography sx={{ mt: 2 }} color="text.secondary">
              {t("projects.empty")}
            </Typography>
          )}
        </List>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("projects.createTitle")}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            margin="normal"
            label={t("projects.name")}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          {create.error && <ErrorState message={getErrorMessage(create.error)} />}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)} sx={{ cursor: "pointer" }}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            disabled={create.isPending || name.trim().length === 0}
            onClick={async () => {
              await create.mutateAsync({ name: name.trim() });
              setName("");
              setOpen(false);
            }}
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

