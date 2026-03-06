import { useQuery } from "@tanstack/react-query";
import { http } from "../../shared/api/http";

export type TimeSeriesPoint = { ts: string; value: number };

export type DashboardMetricsResponse = {
  log_volume: TimeSeriesPoint[];
  error_rate: TimeSeriesPoint[];
};

export function useDashboardMetrics(minutes = 30) {
  return useQuery({
    queryKey: ["metrics", "dashboard", minutes],
    queryFn: async () => {
      const { data } = await http.get<DashboardMetricsResponse>(
        `/api/v1/metrics/dashboard?minutes=${minutes}`
      );
      return data;
    },
  });
}
