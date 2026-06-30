import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { ShieldCheck, Loader2 } from "lucide-react";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", phone: "", password: "" });
  const [loading, setLoading] = useState(false);

  const onChange = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await register({ ...form, role: "customer" });
      toast.success(`Welcome, ${u.full_name}`);
      navigate("/dashboard");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Registration failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex" data-testid="register-page">
      <div className="hidden lg:flex flex-1 bg-gradient-to-br from-blue-600 via-blue-500 to-indigo-600 text-white p-12 flex-col justify-between">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center"><ShieldCheck className="w-5 h-5" /></div>
          <span className="font-heading font-semibold text-lg">ComplaintIQ</span>
        </Link>
        <div>
          <h2 className="font-heading text-4xl font-semibold leading-tight">Start in 30 seconds.</h2>
          <p className="mt-4 text-white/80 text-base max-w-md">Create a customer account, submit your first complaint and watch the multi-agent pipeline analyze it in real time.</p>
        </div>
        <div className="text-white/70 text-sm">No credit card · Demo seed included</div>
      </div>
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <h1 className="font-heading text-3xl font-semibold text-slate-900">Create your account</h1>
          <p className="text-slate-600 mt-1 text-sm">Customers only. Staff accounts are seeded by admin.</p>
          <form onSubmit={submit} className="mt-8 space-y-4">
            <div>
              <label className="label-field">Full name</label>
              <input data-testid="reg-fullname" className="input-field" value={form.full_name} onChange={onChange("full_name")} required minLength={2} />
            </div>
            <div>
              <label className="label-field">Email</label>
              <input data-testid="reg-email" className="input-field" type="email" value={form.email} onChange={onChange("email")} required />
            </div>
            <div>
              <label className="label-field">Phone (optional)</label>
              <input data-testid="reg-phone" className="input-field" value={form.phone} onChange={onChange("phone")} />
            </div>
            <div>
              <label className="label-field">Password</label>
              <input data-testid="reg-password" className="input-field" type="password" value={form.password} onChange={onChange("password")} required minLength={6} />
            </div>
            <button type="submit" data-testid="reg-submit" disabled={loading} className="btn-primary w-full">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Create account"}
            </button>
          </form>
          <p className="text-sm text-slate-500 mt-6 text-center">
            Already have an account? <Link to="/login" data-testid="reg-login-link" className="text-blue-600 font-medium">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
