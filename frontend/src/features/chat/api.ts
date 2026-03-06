import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../shared/api/http";
import { getAccessToken } from "../../shared/auth/storage";

export type ChatSession = {
  id: number;
  tenant_id: number;
  project_id: number | null;
  title: string;
  created_at: string;
};

export type ChatMessage = {
  id: number;
  session_id: number;
  role: string;
  content: string;
  created_at: string;
  metadata_json: Record<string, unknown> | null;
};

export type SessionsListResponse = { items: ChatSession[] };
export type MessagesListResponse = { items: ChatMessage[] };

const baseURL = import.meta.env.DEV
  ? ""
  : ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "");

export function useChatSessions(project_id?: number | null) {
  return useQuery({
    queryKey: ["chat-sessions", project_id],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (project_id != null) params.set("project_id", String(project_id));
      const { data } = await http.get<SessionsListResponse>(
        `/api/v1/chat/sessions?${params.toString()}`,
      );
      return data;
    },
  });
}

export function useChatMessages(sessionId: number | null) {
  return useQuery({
    queryKey: ["chat-messages", sessionId],
    queryFn: async () => {
      if (sessionId == null) return { items: [] };
      const { data } = await http.get<MessagesListResponse>(
        `/api/v1/chat/sessions/${sessionId}/messages`,
      );
      return data;
    },
    enabled: sessionId != null,
  });
}

export function useCreateChatSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { project_id?: number | null; title?: string | null }) => {
      const { data } = await http.post<ChatSession>("/api/v1/chat/sessions", {
        project_id: body.project_id ?? null,
        title: body.title ?? "",
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
  });
}

export function useDeleteChatSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (sessionId: number) => {
      await http.delete(`/api/v1/chat/sessions/${sessionId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      queryClient.invalidateQueries({ queryKey: ["chat-messages"] });
    },
  });
}

export async function sendChatMessage(
  sessionId: number,
  content: string,
  options: { stream?: boolean } = {},
): Promise<ChatMessage> {
  const params = new URLSearchParams();
  if (options.stream) params.set("stream", "true");
  const { data } = await http.post<ChatMessage>(
    `/api/v1/chat/sessions/${sessionId}/messages?${params.toString()}`,
    { content },
  );
  return data;
}

export async function sendChatMessageStream(
  sessionId: number,
  content: string,
  onDelta: (chunk: string) => void,
  onDone: (messageId: number) => void,
): Promise<void> {
  const token = getAccessToken();
  const url = `${baseURL}/api/v1/chat/sessions/${sessionId}/messages?stream=true`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(res.statusText);
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No body");
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const json = JSON.parse(line.slice(6));
          if (json.delta != null) onDelta(json.delta);
          if (json.done === true && json.message_id != null) onDone(json.message_id);
        } catch {
          // ignore parse errors
        }
      }
    }
  }
}
