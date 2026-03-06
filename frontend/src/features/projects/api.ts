import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../shared/api/http";

export type Project = {
  id: number;
  name: string;
  created_at: string;
};

export type IngestToken = {
  id: number;
  name: string | null;
  token: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const { data } = await http.get<Project[]>("/api/v1/projects");
      return data;
    },
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { name: string }) => {
      const { data } = await http.post<Project>("/api/v1/projects", payload);
      return data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useProjectTokens(projectId: number) {
  return useQuery({
    queryKey: ["projects", projectId, "tokens"],
    queryFn: async () => {
      const { data } = await http.get<IngestToken[]>(`/api/v1/projects/${projectId}/tokens`);
      return data;
    },
    enabled: Number.isFinite(projectId) && projectId > 0,
  });
}

export function useCreateToken(projectId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { name: string | null }) => {
      const { data } = await http.post<IngestToken>(`/api/v1/projects/${projectId}/tokens`, payload);
      return data;
    },
    onSuccess: async (created) => {
      qc.setQueryData<IngestToken[] | undefined>(["projects", projectId, "tokens"], (old) => {
        const base = old ?? [];
        const item: IngestToken = {
          id: created.id,
          name: created.name,
          token: "hidden",
          last_used_at: created.last_used_at,
          revoked_at: created.revoked_at,
        };
        return [...base, item];
      });
      await qc.invalidateQueries({ queryKey: ["projects", projectId, "tokens"] });
    },
  });
}

export function useRevokeToken(projectId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (tokenId: number) => {
      await http.post(`/api/v1/projects/${projectId}/tokens/${tokenId}/revoke`);
      return tokenId;
    },
    onSuccess: async (tokenId) => {
      qc.setQueryData<IngestToken[] | undefined>(["projects", projectId, "tokens"], (old) =>
        old?.map((t) =>
          t.id === tokenId ? { ...t, revoked_at: new Date().toISOString() } : t,
        ) ?? old,
      );
      await qc.invalidateQueries({ queryKey: ["projects", projectId, "tokens"] });
    },
  });
}

