import { Delete as DeleteIcon } from "@mui/icons-material";
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  MenuItem,
  Pagination,
  Paper,
  Table,
  TableBody,
  TableContainer,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getErrorMessage } from "../../shared/api/errors";
import { ErrorState, LoadingState } from "../../shared/components/States";
import { formatDateTime, formatNumber } from "../../shared/utils/format";
import { useProjects } from "../projects/api";
import {
  IssueSeverity,
  IssueStatus,
  IssuesSortBy,
  IssuesStatusFilter,
  useDeleteIssueMutation,
  useIssues,
} from "./api";

function severityColor(s: IssueSeverity): "default" | "warning" | "error" {
  if (s === "critical" || s === "high") return "error";
  if (s === "medium") return "warning";
  return "default";
}

function statusColor(s: IssueStatus): "default" | "success" | "warning" {
  if (s === "resolved") return "success";
  if (s === "snoozed") return "warning";
  return "default";
}

export function IssuesListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const projects = useProjects();
  const deleteIssue = useDeleteIssueMutation();

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [issueToDelete, setIssueToDelete] = useState<number | null>(null);

  const [projectId, setProjectId] = useState<number | "all">("all");
  const [statusFilter, setStatusFilter] = useState<IssuesStatusFilter>("all");
  const [sortBy, setSortBy] = useState<IssuesSortBy>("priority");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const list = useIssues({
    projectId: projectId === "all" ? null : projectId,
    page,
    pageSize,
    statusFilter,
    sortBy,
  });

  const projectNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const p of projects.data ?? []) map.set(p.id, p.name);
    return map;
  }, [projects.data]);

  return (
    <Box sx={{ pt: 2 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 1 }}>
        <Typography variant="h5">{t("issues.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
      </Box>
      <Box sx={{ display: "flex", gap: 2, mb: 2, flexWrap: "wrap", alignItems: "flex-end" }}>
        <Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
            {t("issues.filterStatus")}
          </Typography>
          <TextField
            select
            variant="filled"
            size="small"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as IssuesStatusFilter);
              setPage(1);
            }}
            sx={{ minWidth: 120 }}
          >
            <MenuItem value="all">{t("issues.statusAll")}</MenuItem>
            <MenuItem value="open">{t("issues.statusOpen")}</MenuItem>
            <MenuItem value="closed">{t("issues.statusClosed")}</MenuItem>
          </TextField>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
            {t("issues.sortBy")}
          </Typography>
          <TextField
            select
            variant="filled"
            size="small"
            value={sortBy}
            onChange={(e) => {
              setSortBy(e.target.value as IssuesSortBy);
              setPage(1);
            }}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="priority">{t("issues.sortPriority")}</MenuItem>
            <MenuItem value="severity">{t("issues.sortSeverity")}</MenuItem>
            <MenuItem value="last_seen">{t("issues.sortLastSeen")}</MenuItem>
          </TextField>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
            {t("issues.project")}
          </Typography>
          <TextField
            select
            variant="filled"
            size="small"
            value={projectId}
            onChange={(e) => {
              const v = e.target.value;
              setProjectId(v === "all" ? "all" : Number(v));
              setPage(1);
            }}
            sx={{ minWidth: 240 }}
          >
            <MenuItem value="all">{t("issues.allProjects")}</MenuItem>
            {(projects.data ?? []).map((p) => (
              <MenuItem key={p.id} value={p.id}>
                {p.name}
              </MenuItem>
            ))}
          </TextField>
        </Box>
      </Box>

      {list.isLoading && <LoadingState label={t("common.loading")} />}
      {list.error && <ErrorState message={getErrorMessage(list.error)} />}

      {list.data && (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 0 }}>
          <Paper variant="outlined" sx={{ overflow: "hidden" }}>
            <TableContainer sx={{ height: 440 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>{t("issues.issue")}</TableCell>
                    <TableCell>{t("issues.project")}</TableCell>
                    <TableCell>{t("issues.severity")}</TableCell>
                    <TableCell>{t("issues.status")}</TableCell>
                    <TableCell>{t("issues.lastSeen")}</TableCell>
                    <TableCell align="right">{t("issues.total")}</TableCell>
                    <TableCell align="right">{t("issues.priority")}</TableCell>
                    <TableCell padding="none" width={48} />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {list.data.items.map((it) => (
                    <TableRow
                      key={it.id}
                      hover
                      sx={{ cursor: "pointer" }}
                      onClick={() => navigate(`/issues/${it.id}`)}
                    >
                      <TableCell>{it.title}</TableCell>
                      <TableCell>{projectNameById.get(it.project_id) ?? `#${it.project_id}`}</TableCell>
                      <TableCell>
                        <Chip size="small" color={severityColor(it.severity)} label={it.severity} />
                      </TableCell>
                      <TableCell>
                        <Chip size="small" color={statusColor(it.status)} label={it.status} />
                      </TableCell>
                      <TableCell>{formatDateTime(it.last_seen)}</TableCell>
                      <TableCell align="right">{formatNumber(it.total_count)}</TableCell>
                      <TableCell align="right">{it.priority_score.toFixed(2)}</TableCell>
                      <TableCell padding="none" onClick={(e) => e.stopPropagation()}>
                        <IconButton
                          size="small"
                          color="error"
                          aria-label={t("issues.delete")}
                          onClick={() => {
                            setIssueToDelete(it.id);
                            setDeleteDialogOpen(true);
                          }}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                  {list.data.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={8}>
                        <Typography color="text.secondary">{t("issues.empty")}</Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
          <Box sx={{ display: "flex", justifyContent: "flex-end", py: 2, flexShrink: 0 }}>
            <Pagination
              count={Math.ceil((list.data?.aggregates?.total ?? 0) / pageSize)}
              page={page}
              onChange={(_e, p) => setPage(p)}
            />
          </Box>
        </Box>
      )}

      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>{t("issues.deleteConfirmTitle", "Delete issue?")}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t(
              "issues.deleteConfirmMessage",
              "This action cannot be undone. The issue and its related data will be permanently deleted."
            )}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} sx={{ cursor: "pointer" }}>
            {t("common.cancel")}
          </Button>
          <Button
            color="error"
            variant="contained"
            disabled={deleteIssue.isPending || issueToDelete == null}
            onClick={async () => {
              if (issueToDelete != null) {
                await deleteIssue.mutateAsync(issueToDelete);
                setDeleteDialogOpen(false);
                setIssueToDelete(null);
              }
            }}
            sx={{ cursor: "pointer" }}
          >
            {deleteIssue.isPending ? t("common.loading") : t("issues.delete")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
