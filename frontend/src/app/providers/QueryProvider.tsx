import { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const client = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 15_000,
    },
  },
});

export const QueryProvider = ({ children }: PropsWithChildren) => {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

