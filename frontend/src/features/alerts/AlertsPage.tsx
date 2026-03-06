import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  MenuItem,
  Paper,
  Switch,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { getErrorMessage } from "../../shared/api/errors";
import { ErrorState, LoadingState } from "../../shared/components/States";
import { formatDateTime } from "../../shared/utils/format";
import { useProjects } from "../projects/api";
import {
  AlertKind,
  useAlertEvents,
  useAlertRules,
  useChannels,
  useCreateAlertRule,
  useCreateChannel,
  useDeleteAlertRule,
  useUpdateAlertRule,
  useUpdateChannel,
} from "./api";

function AlertRuleRow({
  rule,
  projectName,
}: {
  rule: {
    id: number;
    project_id: number;
    name: string;
    kind: string;
    threshold: number;
    enabled: boolean;
  };
  projectName: string;
}) {
  const { t } = useTranslation();
  const upd = useUpdateAlertRule(rule.id);
  const del = useDeleteAlertRule(rule.id);
  const [name, setName] = useState(rule.name);
  const [threshold, setThreshold] = useState(rule.threshold);

  return (
    <TableRow>
      <TableCell>
        <TextField
          size="small"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => {
            if (name.trim() !== rule.name) upd.mutate({ name: name.trim() });
          }}
          sx={{ width: 280 }}
        />
      </TableCell>
      <TableCell>{projectName}</TableCell>
      <TableCell>{rule.kind}</TableCell>
      <TableCell align="right">
        <TextField
          size="small"
          type="number"
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value))}
          onBlur={() => {
            if (Number(threshold) !== rule.threshold) upd.mutate({ threshold: Number(threshold) });
          }}
          sx={{ width: 120 }}
        />
      </TableCell>
      <TableCell>
        <Switch checked={rule.enabled} onChange={(_e, checked) => upd.mutate({ enabled: checked })} />
      </TableCell>
      <TableCell align="right">
        <Button color="error" size="small" onClick={() => del.mutate()}>
          {t("alerts.delete")}
        </Button>
      </TableCell>
    </TableRow>
  );
}

function ChannelRow({ channel }: { channel: { id: number; display_name: string; enabled: boolean } }) {
  const { t } = useTranslation();
  const upd = useUpdateChannel(channel.id);
  return (
    <TableRow>
      <TableCell>{channel.display_name}</TableCell>
      <TableCell>
        <FormControlLabel
          control={<Switch checked={channel.enabled} onChange={(_e, checked) => upd.mutate({ enabled: checked })} />}
          label={channel.enabled ? t("alerts.on") : t("alerts.off")}
        />
      </TableCell>
    </TableRow>
  );
}

export function AlertsPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState(0);

  const projects = useProjects();
  const projectNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const p of projects.data ?? []) map.set(p.id, p.name);
    return map;
  }, [projects.data]);

  const [rulesProjectId, setRulesProjectId] = useState<number | "all">("all");
  const rules = useAlertRules(rulesProjectId === "all" ? null : rulesProjectId);
  const createRule = useCreateAlertRule();

  const [createRuleOpen, setCreateRuleOpen] = useState(false);
  const [ruleProjectId, setRuleProjectId] = useState<number | "">("");
  const [ruleName, setRuleName] = useState("");
  const [ruleKind, setRuleKind] = useState<AlertKind>("count_5m");
  const [ruleThreshold, setRuleThreshold] = useState(10);

  const channels = useChannels();
  const createChannel = useCreateChannel();
  const [createChannelOpen, setCreateChannelOpen] = useState(false);
  const [slackWebhookUrl, setSlackWebhookUrl] = useState("");

  const [sinceHours, setSinceHours] = useState<number | "">("");
  const events = useAlertEvents({ sinceHours: sinceHours === "" ? null : sinceHours, limit: 50 });

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        {t("alerts.title")}
      </Typography>

      <Paper variant="outlined" sx={{ mb: 2 }}>
        <Tabs value={tab} onChange={(_e, v) => setTab(v)} aria-label="alerts tabs">
          <Tab label={t("alerts.rules")} />
          <Tab label={t("alerts.channels")} />
          <Tab label={t("alerts.events")} />
        </Tabs>
      </Paper>

      {tab === 0 && (
        <Box>
          <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
            <TextField
              select
              size="small"
              label={t("alerts.project")}
              value={rulesProjectId}
              onChange={(e) => setRulesProjectId(e.target.value === "all" ? "all" : Number(e.target.value))}
              sx={{ minWidth: 240 }}
            >
              <MenuItem value="all">{t("alerts.allProjects")}</MenuItem>
              {(projects.data ?? []).map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}
                </MenuItem>
              ))}
            </TextField>
            <Box sx={{ flexGrow: 1 }} />
            <Button variant="contained" onClick={() => setCreateRuleOpen(true)}>
              {t("alerts.createRule")}
            </Button>
          </Box>

          {rules.isLoading && <LoadingState label={t("common.loading")} />}
          {rules.error && <ErrorState message={getErrorMessage(rules.error)} />}
          {rules.data && (
            <Paper variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("alerts.ruleName")}</TableCell>
                    <TableCell>{t("alerts.project")}</TableCell>
                    <TableCell>{t("alerts.kind")}</TableCell>
                    <TableCell align="right">{t("alerts.threshold")}</TableCell>
                    <TableCell>{t("alerts.enabled")}</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rules.data.map((r) => (
                    <AlertRuleRow
                      key={r.id}
                      rule={r}
                      projectName={projectNameById.get(r.project_id) ?? `#${r.project_id}`}
                    />
                  ))}
                  {rules.data.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6}>
                        <Typography color="text.secondary">{t("alerts.noRules")}</Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </Paper>
          )}

          <Dialog open={createRuleOpen} onClose={() => setCreateRuleOpen(false)} maxWidth="sm" fullWidth>
            <DialogTitle>{t("alerts.createRuleTitle")}</DialogTitle>
            <DialogContent>
              <TextField
                select
                fullWidth
                margin="normal"
                label={t("alerts.project")}
                value={ruleProjectId}
                onChange={(e) => setRuleProjectId(Number(e.target.value))}
              >
                {(projects.data ?? []).map((p) => (
                  <MenuItem key={p.id} value={p.id}>
                    {p.name}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                fullWidth
                margin="normal"
                label={t("alerts.ruleName")}
                value={ruleName}
                onChange={(e) => setRuleName(e.target.value)}
              />
              <TextField
                select
                fullWidth
                margin="normal"
                label={t("alerts.kind")}
                value={ruleKind}
                onChange={(e) => setRuleKind(e.target.value as AlertKind)}
              >
                <MenuItem value="count_5m">{t("alerts.kindCount5m")}</MenuItem>
                <MenuItem value="spike">{t("alerts.kindSpike")}</MenuItem>
              </TextField>
              <TextField
                fullWidth
                margin="normal"
                label={t("alerts.threshold")}
                type="number"
                value={ruleThreshold}
                onChange={(e) => setRuleThreshold(Number(e.target.value))}
              />
              {createRule.error && <ErrorState message={getErrorMessage(createRule.error)} />}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setCreateRuleOpen(false)}>{t("common.cancel")}</Button>
              <Button
                variant="contained"
                disabled={createRule.isPending || ruleProjectId === "" || ruleName.trim().length === 0}
                onClick={async () => {
                  await createRule.mutateAsync({
                    project_id: Number(ruleProjectId),
                    name: ruleName.trim(),
                    kind: ruleKind,
                    threshold: ruleThreshold,
                  });
                  setRuleName("");
                  setRuleProjectId("");
                  setCreateRuleOpen(false);
                }}
              >
                {t("common.save")}
              </Button>
            </DialogActions>
          </Dialog>
        </Box>
      )}

      {tab === 1 && (
        <Box>
          <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
            <Typography color="text.secondary">{t("alerts.channelsHint")}</Typography>
            <Box sx={{ flexGrow: 1 }} />
            <Button variant="contained" onClick={() => setCreateChannelOpen(true)}>
              {t("alerts.createChannel")}
            </Button>
          </Box>

          {channels.isLoading && <LoadingState label={t("common.loading")} />}
          {channels.error && <ErrorState message={getErrorMessage(channels.error)} />}
          {channels.data && (
            <Paper variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("alerts.channel")}</TableCell>
                    <TableCell>{t("alerts.enabled")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {channels.data.map((ch) => (
                    <ChannelRow key={ch.id} channel={ch} />
                  ))}
                  {channels.data.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={2}>
                        <Typography color="text.secondary">{t("alerts.noChannels")}</Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </Paper>
          )}

          <Dialog open={createChannelOpen} onClose={() => setCreateChannelOpen(false)} maxWidth="sm" fullWidth>
            <DialogTitle>{t("alerts.createChannelTitle")}</DialogTitle>
            <DialogContent>
              <Typography color="text.secondary">{t("alerts.slackWebhook")}</Typography>
              <Divider sx={{ my: 2 }} />
              <TextField
                fullWidth
                margin="normal"
                label={t("alerts.slackWebhookUrl")}
                value={slackWebhookUrl}
                onChange={(e) => setSlackWebhookUrl(e.target.value)}
                placeholder="https://hooks.slack.com/services/..."
              />
              {createChannel.error && <ErrorState message={getErrorMessage(createChannel.error)} />}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setCreateChannelOpen(false)}>{t("common.cancel")}</Button>
              <Button
                variant="contained"
                disabled={createChannel.isPending || slackWebhookUrl.trim().length === 0}
                onClick={async () => {
                  await createChannel.mutateAsync({ kind: "slack_webhook", slack_webhook_url: slackWebhookUrl.trim() });
                  setSlackWebhookUrl("");
                  setCreateChannelOpen(false);
                }}
              >
                {t("common.save")}
              </Button>
            </DialogActions>
          </Dialog>
        </Box>
      )}

      {tab === 2 && (
        <Box>
          <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
            <TextField
              size="small"
              type="number"
              label={t("alerts.sinceHours")}
              value={sinceHours}
              onChange={(e) => setSinceHours(e.target.value === "" ? "" : Number(e.target.value))}
              sx={{ width: 180 }}
            />
            <Box sx={{ flexGrow: 1 }} />
            <Button variant="outlined" onClick={() => events.refetch()}>
              {t("alerts.refresh")}
            </Button>
          </Box>

          {events.isLoading && <LoadingState label={t("common.loading")} />}
          {events.error && <ErrorState message={getErrorMessage(events.error)} />}
          {events.data && (
            <Paper variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t("alerts.triggeredAt")}</TableCell>
                    <TableCell>{t("alerts.ruleId")}</TableCell>
                    <TableCell>{t("alerts.issueId")}</TableCell>
                    <TableCell>{t("alerts.payload")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {events.data.map((ev) => (
                    <TableRow key={ev.id}>
                      <TableCell>{formatDateTime(ev.triggered_at)}</TableCell>
                      <TableCell>{ev.rule_id}</TableCell>
                      <TableCell>{ev.issue_id}</TableCell>
                      <TableCell>
                        <Typography component="pre" sx={{ m: 0, fontSize: 12, whiteSpace: "pre-wrap" }}>
                          {JSON.stringify(ev.payload, null, 2)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                  {events.data.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4}>
                        <Typography color="text.secondary">{t("alerts.noEvents")}</Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </Paper>
          )}
        </Box>
      )}
    </Box>
  );
}

