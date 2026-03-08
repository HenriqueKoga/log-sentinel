import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../shared/api/http";

export type PlanType = "monthly" | "yearly" | "unlimited";
export type PlanStatus = "active";

export type BillingPlan = {
  plan_type: PlanType;
  status: PlanStatus;
  starts_at: string;
  ends_at: string | null;
  enable_llm_enrichment: boolean;
  monthly_credits_limit: number;
};

export type BillingUsage = {
  plan_type: PlanType;
  period_start: string;
  events_ingested: number;
  llm_enrichments: number;
};

export type CreditBar = {
  credits_used: number;
  credits_limit: number;
  percentage: number;
  period_start: string;
  period_end: string;
};

export type SettingsUpdate = {
  enable_llm_enrichment: boolean;
};

export type LlmUsageTotals = {
  input_tokens: number;
  output_tokens: number;
  total_cost: number;
  credits_used: number;
};

export type ModelBreakdown = {
  model_id: number;
  model_name: string;
  display_name: string;
  input_tokens: number;
  output_tokens: number;
  total_cost: number;
  credits_used: number;
};

export type FeatureBreakdown = {
  feature: string;
  input_tokens: number;
  output_tokens: number;
  total_cost: number;
  credits_used: number;
};

export type LlmUsageSummary = {
  period_start: string;
  period_end: string;
  totals: LlmUsageTotals;
  by_model: ModelBreakdown[];
  by_feature: FeatureBreakdown[];
};

export type LlmModelOut = {
  id: number;
  provider: string;
  model_name: string;
  display_name: string;
  input_token_price: number;
  output_token_price: number;
  currency: string;
  is_active: boolean;
  supports_usage_tracking: boolean;
  created_at: string;
  updated_at: string;
};

export type CreditPolicyOut = {
  id: number;
  name: string;
  currency: string;
  credits_per_currency_unit: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
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

export function useCreditBar() {
  return useQuery({
    queryKey: ["billing", "credit-bar"],
    queryFn: async () => {
      const { data } = await http.get<CreditBar>("/api/v1/billing/credit-bar");
      return data;
    },
  });
}

export function useLlmUsageSummary(params?: { from?: string; to?: string; project_id?: number }) {
  return useQuery({
    queryKey: ["billing", "llm-usage", params],
    queryFn: async () => {
      const { data } = await http.get<LlmUsageSummary>("/api/v1/billing/llm-usage", { params });
      return data;
    },
  });
}

export function useLlmModels(activeOnly = true) {
  return useQuery({
    queryKey: ["billing", "llm-models", activeOnly],
    queryFn: async () => {
      const { data } = await http.get<{ items: LlmModelOut[] }>("/api/v1/billing/llm-models", {
        params: { active_only: activeOnly },
      });
      return data.items;
    },
  });
}

export function useCreditPolicy() {
  return useQuery({
    queryKey: ["billing", "credit-policy"],
    queryFn: async () => {
      const { data } = await http.get<CreditPolicyOut | null>("/api/v1/billing/credit-policy");
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
