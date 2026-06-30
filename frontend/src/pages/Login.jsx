import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { ShieldCheck, Loader2 } from "lucide-react";

const DEMO = [
  { role: "Administrator", email: "admin@complaintiq.com", password: "Admin@123" },
  { role: "Manager", email: "manager@complaintiq.com", password: "Manager@123" },
  { role: "Support", email: "support@complaintiq.com", password: "Support@123" },
  { role: "Customer", email: "customer@complaintiq.com", password: "Customer@123" },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e?.preventDefault();
    setLoading(true);
    try {
      const u = await login(email.trim(), password);
      toast.success(`Welcome back, ${u.full_name}`);
      const dest = u.role === "manager" || u.role === "admin" ? "/admin" : "/dashboard";
      navigate(location.state?.from?.pathname || dest, { replace: true });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally { setLoading(false); }
  };

  const fillDemo = (d) => { setEmail(d.email); setPassword(d.password); };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex" data-testid="login-page">
      <div className="hidden lg:flex flex-1 bg-gradient-to-br from-blue-600 via-blue-500 to-indigo-600 text-white p-12 flex-col justify-between">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center"><ShieldCheck className="w-5 h-5" /></div>
          <span className="font-heading font-semibold text-lg">ComplaintIQ</span>
        </Link>
        <div>
          <h2 className="font-heading text-4xl font-semibold leading-tight">Agentic AI for consumer complaint intelligence.</h2>
          <p className="mt-4 text-white/80 text-base max-w-md">Sign in to submit, analyze, and resolve complaints with a 10-agent LangGraph workflow grounded in your policy knowledge base.</p>
        </div>
        <div className="text-white/70 text-sm">Multi-Agent Systems · NLP · RAG · Explainable AI</div>
      </div>
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <h1 className="font-heading text-3xl font-semibold text-slate-900">Welcome back</h1>
          <p className="text-slate-600 mt-1 text-sm">Sign in to your account to continue</p>
          <form onSubmit={submit} className="mt-8 space-y-5">
            <div>
              <label className="label-field" htmlFor="email">Email</label>
              <input id="email" data-testid="login-email" className="input-field" value={email} onChange={(e)=>setEmail(e.target.value)} type="email" required />
            </div>
            <div>
              <label className="label-field" htmlFor="password">Password</label>
              <input id="password" data-testid="login-password" className="input-field" value={password} onChange={(e)=>setPassword(e.target.value)} type="password" required />
            </div>
            <button type="submit" data-testid="login-submit" disabled={loading} className="btn-primary w-full">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Sign in"}
            </button>
          </form>
          <p className="text-sm text-slate-500 mt-6 text-center">
            New here? <Link to="/register" data-testid="login-register-link" className="text-blue-600 font-medium">Create an account</Link>
          </p>
          <div className="mt-8 card-soft p-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Demo accounts</div>
            <div className="grid grid-cols-2 gap-2">
              {DEMO.map((d) => (
                <button type="button" key={d.role} onClick={() => fillDemo(d)} data-testid={`demo-${d.role.toLowerCase()}`} className="text-left px-3 py-2 rounded-[10px] border border-slate-100 hover:bg-slate-50 transition-colors">
                  <div className="text-xs font-medium text-slate-700">{d.role}</div>
                  <div className="text-[11px] text-slate-500 truncate">{d.email}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
