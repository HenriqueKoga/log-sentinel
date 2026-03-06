import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useIsFetching } from "@tanstack/react-query";

export function RouteTransitionLoader() {
  const location = useLocation();
  const lastPathRef = useRef(location.pathname);
  const [visible, setVisible] = useState(false);
  const isFetching = useIsFetching();

  useEffect(() => {
    if (location.pathname === lastPathRef.current) return;
    lastPathRef.current = location.pathname;
    setVisible(true);
  }, [location.pathname]);

  useEffect(() => {
    if (!visible) return;
    if (isFetching === 0) {
      const timeout = setTimeout(() => setVisible(false), 100);
      return () => clearTimeout(timeout);
    }
    return;
  }, [visible, isFetching]);

  if (!visible) return null;

  return (
    <div className="pointer-events-none fixed inset-0 z-[200] flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="relative flex h-20 w-20 items-center justify-center">
        <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-fuchsia-500 via-sky-500 to-violet-500 opacity-60 blur-xl" />
        <div className="absolute inset-1 rounded-full border border-white/10 bg-slate-950/80" />
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-sky-400 border-t-transparent" />
      </div>
    </div>
  );
}

