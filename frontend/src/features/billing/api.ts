import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../shared/api/http";

export type PlanType = "monthly" | "yearly" | "unlimited";
export type PlanStatus = "active";

export type BillingPlan = {
  plan_type: PlanType;
  status: PlanStatus;
  starts_at: string;
  ends_at: string | null;
  limit: number | null;
  enable_llm_enrichment: boolean;
};

export type BillingUsage = {
  plan_type: PlanType;
  period_start: string;
  used: number;
  limit: number | null;
  events_ingested: number;
  llm_enrichments: number;
};

export type SettingsUpdate = {
  enable_llm_enrichment: boolean;
};

export function useBillingPlan() {
  return useQuery({
    queryKey: ["billing", "plan"],
    queryFn: async () => {
      const { data } = await http.get<BillingPlan>("/api/v1/billing/plan");
      return data;
    },
  });
}

export function useBillingUsage() {
  return useQuery({
    queryKey: ["billing", "usage"],
    queryFn: async () => {
      const { data } = await http.get<BillingUsage>("/api/v1/billing/usage");
      return data;
    },
  });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: SettingsUpdate) => {
      const { data } = await http.patch<BillingPlan>("/api/v1/billing/settings", body);
      return data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["billing"] });
    },
  });
}

