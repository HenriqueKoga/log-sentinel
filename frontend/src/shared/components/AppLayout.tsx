import { useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard,
  Activity,
  AlertTriangle,
  Bell,
  Brain,
  MessageCircle,
  Server,
  Plug,
  Settings2,
  CreditCard,
} from "lucide-react";
import { useAuth } from "../../app/providers/useAuth";
import { useBillingPlan } from "../../features/billing/api";

const baseNavItems = [
  { to: "/", key: "dashboard", icon: LayoutDashboard },
  { to: "/logs", key: "logs", icon: Activity },
  { to: "/issues", key: "issues", icon: AlertTriangle },
  { to: "/alerts", key: "alerts", icon: Bell },
  { to: "/ai", key: "aiInsights", icon: Brain, llmOnly: true },
  { to: "/chat", key: "chatLogs", icon: MessageCircle, llmOnly: true },
  { to: "/sources", key: "sources", icon: Server },
  { to: "/integrations", key: "integrations", icon: Plug },
  { to: "/settings", key: "settings", icon: Settings2 },
  { to: "/billing", key: "billing", icon: CreditCard },
];

function ToggleIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={collapsed ? "transform rotate-180 transition-transform" : "transition-transform"}
      aria-hidden="true"
    >
      <path d="M5 4v16" />
      <path d="M15 8l-4 4 4 4" />
      <path d="M19 8l-4 4 4 4" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M9 3h9a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H9" />
      <path d="M16 12H3" />
      <path d="M7 8l-4 4 4 4" />
    </svg>
  );
}

export const AppLayout = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const auth = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const plan = useBillingPlan();
  const llmEnabled = plan.data?.enable_llm_enrichment ?? false;
  const navItems = baseNavItems.filter(
    (item) => !("llmOnly" in item && item.llmOnly) || llmEnabled,
  );

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <aside
        className={`flex flex-col border-r border-white/5 bg-black/30 backdrop-blur-md transition-all duration-200 ${
          collapsed ? "w-16" : "w-64"
        }`}
      >
        {collapsed ? (
          <div className="flex h-24 items-center justify-center px-0">
            <button
              type="button"
              onClick={() => setCollapsed((v) => !v)}
              className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border border-white/20 bg-black/60 text-slate-100 shadow-lg hover:border-white/40 hover:bg-black/80"
              aria-label="Expand sidebar"
            >
              <ToggleIcon collapsed />
            </button>
          </div>
        ) : (
          <div className="flex h-24 items-stretch justify-between px-0">
            <div className="flex flex-1 items-stretch overflow-hidden">
              <img
                src="/logo_ext.png"
                alt="LogSentinel"
                className="h-full w-full object-cover drop-shadow-lg"
              />
            </div>
            <button
              type="button"
              onClick={() => setCollapsed((v) => !v)}
              className="mr-2 ml-2 flex h-8 w-8 cursor-pointer self-center items-center justify-center rounded-full border border-white/20 bg-black/60 text-slate-100 shadow-lg hover:border-white/40 hover:bg-black/80"
              aria-label="Collapse sidebar"
            >
              <ToggleIcon collapsed={false} />
            </button>
          </div>
        )}
        <nav className="flex-1 space-y-1 px-2 py-4">
          {navItems.map(({ to, key, icon: Icon }) => (
            <button
              key={to}
              type="button"
              onClick={() => navigate(to)}
              className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-400 transition-colors hover:bg-white/5 hover:text-slate-100"
            >
              <Icon className="h-6 w-6" />
              {!collapsed && <span>{t(`nav.${key}` as const)}</span>}
            </button>
          ))}
        </nav>
        <div className="border-t border-white/5 px-3 py-3 text-xs text-slate-500">
          {!collapsed && <span>Environment: local</span>}
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-white/5 bg-black/20 px-6 backdrop-blur-md">
          <div className="text-sm text-slate-400" />
          <div className="flex items-center gap-3 text-sm">
            <button
              type="button"
              onClick={() => {
                auth.logout();
                navigate("/login");
              }}
              className="flex cursor-pointer items-center gap-2 rounded-full border border-primary/40 bg-primary/20 px-5 py-2 text-sm font-semibold text-slate-50 shadow-md hover:border-primary hover:bg-primary/30"
            >
              <LogoutIcon />
              <span>{t("auth.logout")}</span>
            </button>
          </div>
        </header>

        <main className="flex min-h-0 flex-1 flex-col p-6">
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

