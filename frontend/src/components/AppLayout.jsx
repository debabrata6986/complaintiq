import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Bell, BookOpen, Gauge, LayoutDashboard, ListChecks, LogOut, PlusCircle, ShieldCheck, User, Globe, Mic, Building2, BrainCircuit, Paperclip, Zap, Activity } from "lucide-react";

const NAV_BY_ROLE = {
  customer: [
    { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
    { to: "/complaints", label: "My Complaints", icon: ListChecks, testid: "nav-complaints" },
    { to: "/submit", label: "Submit Complaint", icon: PlusCircle, testid: "nav-submit" },
    { to: "/knowledge", label: "Knowledge Base", icon: BookOpen, testid: "nav-kb" },
    { to: "/profile", label: "Profile", icon: User, testid: "nav-profile" },
  ],
  support: [
    { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
    { to: "/complaints", label: "All Complaints", icon: ListChecks, testid: "nav-complaints" },
    { to: "/knowledge", label: "Knowledge Base", icon: BookOpen, testid: "nav-kb" },
    { to: "/profile", label: "Profile", icon: User, testid: "nav-profile" },
  ],
  manager: [
    { to: "/admin", label: "Analytics", icon: Gauge, testid: "nav-admin" },
    { to: "/complaints", label: "All Complaints", icon: ListChecks, testid: "nav-complaints" },
    { to: "/knowledge", label: "Knowledge Base", icon: BookOpen, testid: "nav-kb" },
    { to: "/self-healing", label: "Self-Healing Engine", icon: Activity, testid: "nav-selfhealing" },
    { to: "/realtime-test", label: "Realtime Assistant", icon: Zap, testid: "nav-realtime" },
    { to: "/profile", label: "Profile", icon: User, testid: "nav-profile" },
  ],
  admin: [
    { to: "/admin", label: "Analytics", icon: Gauge, testid: "nav-admin" },
    { to: "/complaints", label: "All Complaints", icon: ListChecks, testid: "nav-complaints" },
    { to: "/knowledge", label: "Knowledge Base", icon: BookOpen, testid: "nav-kb" },
    { to: "/self-healing", label: "Self-Healing Engine", icon: Activity, testid: "nav-selfhealing" },
    { to: "/realtime-test", label: "Realtime Assistant", icon: Zap, testid: "nav-realtime" },
    { to: "/profile", label: "Profile", icon: User, testid: "nav-profile" },
  ],
};

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const navItems = NAV_BY_ROLE[user?.role || "customer"] || [];

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex">
      <aside className="hidden md:flex w-64 flex-col bg-white border-r border-slate-100 sticky top-0 h-screen" data-testid="app-sidebar">
        <Link to="/" className="px-6 pt-6 pb-8 flex items-center gap-2" data-testid="sidebar-logo">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-600 to-blue-500 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-heading font-semibold text-slate-900 text-lg leading-none">ComplaintIQ</div>
            <div className="text-[11px] text-slate-400 mt-1">Agentic AI Platform</div>
          </div>
        </Link>
        <nav className="px-3 flex-1 space-y-1">
          {navItems.map(({ to, label, icon: Icon, testid }) => (
            <NavLink
              key={to}
              to={to}
              data-testid={testid}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-[10px] text-sm transition-colors ${
                  isActive ? "bg-blue-50 text-blue-700 font-medium" : "text-slate-600 hover:bg-slate-50"
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-slate-100 mt-auto">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center text-white text-sm font-medium">
              {user?.full_name?.[0] || "U"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-slate-800 truncate" data-testid="sidebar-username">{user?.full_name}</div>
              <div className="text-xs text-slate-500 capitalize">{user?.role}</div>
            </div>
          </div>
          <button
            data-testid="logout-btn"
            onClick={() => { logout(); navigate("/login"); }}
            className="w-full flex items-center justify-center gap-2 text-sm text-slate-600 hover:text-slate-900 border border-slate-200 rounded-[10px] py-2 hover:bg-slate-50 transition-colors"
          >
            <LogOut className="w-4 h-4" /> Log out
          </button>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="md:hidden bg-white border-b border-slate-100 px-4 py-3 flex items-center justify-between sticky top-0 z-10">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <ShieldCheck className="w-4 h-4 text-white" />
            </div>
            <span className="font-heading font-semibold text-slate-900">ComplaintIQ</span>
          </Link>
          <button onClick={() => { logout(); navigate("/login"); }} className="text-slate-600" data-testid="mobile-logout">
            <LogOut className="w-5 h-5" />
          </button>
        </header>
        <main className="flex-1 px-4 md:px-10 py-8 max-w-[1400px] w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
