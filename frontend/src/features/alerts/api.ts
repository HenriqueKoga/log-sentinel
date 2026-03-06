import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../shared/api/http";

export type AlertKind = "count_5m" | "spike";
export type ChannelKind = "slack_webhook";

export type AlertRule = {
  id: number;
  project_id: number;
  name: string;
  kind: AlertKind;
  threshold: number;
  enabled: boolean;
};

export type NotificationChannel = {
  id: number;
  kind: ChannelKind;
  enabled: boolean;
  display_name: string;
};

export type AlertEvent = {
  id: number;
  issue_id: number;
  rule_id: number;
  triggered_at: string;
  payload: Record<string, unknown>;
};

export function useAlertRules(projectId?: number | null) {
  return useQuery({
    queryKey: ["alerts", "rules", { projectId: projectId ?? null }],
    queryFn: async () => {
      const { data } = await http.get<AlertRule[]>("/api/v1/alerts/rules", {
        params: { project_id: projectId ?? undefined },
      });
      return data;
    },
  });
}

export function useCreateAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { project_id: number; name: string; kind: AlertKind; threshold: number }) => {
      const { data } = await http.post<AlertRule>("/api/v1/alerts/rules", payload);
      return data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["alerts", "rules"] });
    },
  });
}

export function useUpdateAlertRule(ruleId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { name?: string; threshold?: number; enabled?: boolean }) => {
      const { data } = await http.patch<AlertRule>(`/api/v1/alerts/rules/${ruleId}`, payload);
      return data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["alerts", "rules"] });
    },
  });
}

export function useDeleteAlertRule(ruleId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await http.delete(`/api/v1/alerts/rules/${ruleId}`);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["alerts", "rules"] });
    },
  });
}

export function useChannels() {
  return useQuery({
    queryKey: ["alerts", "channels"],
    queryFn: async () => {
      const { data } = await http.get<NotificationChannel[]>("/api/v1/alerts/channels");
      return data;
    },
  });
}

export function useCreateChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { kind: ChannelKind; slack_webhook_url?: string }) => {
      const { data } = await http.post<NotificationChannel>("/api/v1/alerts/channels", payload);
      return data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["alerts", "channels"] });
    },
  });
}

export function useUpdateChannel(channelId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { enabled?: boolean }) => {
      const { data } = await http.patch<NotificationChannel>(`/api/v1/alerts/channels/${channelId}`, payload);
      return data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["alerts", "channels"] });
    },
  });
}

export function useAlertEvents(params: { sinceHours?: number | null; limit?: number }) {
  return useQuery({
    queryKey: ["alerts", "events", { sinceHours: params.sinceHours ?? null, limit: params.limit ?? 50 }],
    queryFn: async () => {
      const { data } = await http.get<AlertEvent[]>("/api/v1/alerts/events", {
        params: { since_hours: params.sinceHours ?? undefined, limit: params.limit ?? 50 },
      });
      return data;
    },
  });
}

