import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Send, Loader2 } from "lucide-react";

const DOMAINS = [
  { v: "ecommerce", l: "E-commerce" }, { v: "banking", l: "Banking" },
  { v: "telecom", l: "Telecom" }, { v: "insurance", l: "Insurance" },
  { v: "healthcare", l: "Healthcare" }, { v: "government", l: "Government" },
  { v: "utilities", l: "Utilities" },
];

const CATEGORIES = ["Refund", "Replacement", "Delivery Delay", "Payment Failure", "Billing Issue", "Warranty", "Fraud", "Account Issue", "Cancellation", "General Complaint"];

export default function SubmitComplaint() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ domain: "ecommerce", category: "", description: "", customer_phone: "" });
  const [loading, setLoading] = useState(false);

  const ch = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (form.description.trim().length < 10) {
      toast.error("Description must be at least 10 characters");
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post("/complaints", form);
      toast.success("Complaint submitted — AI is analyzing");
      navigate(`/complaints/${data.id}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Submission failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="max-w-3xl" data-testid="submit-page">
      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">New complaint</div>
      <h1 className="font-heading text-3xl font-semibold text-slate-900">Submit a complaint</h1>
      <p className="text-slate-600 mt-2">Provide as much detail as possible — order IDs, dates, amounts. The AI will extract entities automatically.</p>

      <form onSubmit={submit} className="card-soft p-6 mt-8 space-y-5">
        <div className="grid md:grid-cols-2 gap-5">
          <div>
            <label className="label-field">Industry / Domain</label>
            <select data-testid="submit-domain" className="input-field" value={form.domain} onChange={ch("domain")}>
              {DOMAINS.map((d) => <option key={d.v} value={d.v}>{d.l}</option>)}
            </select>
          </div>
          <div>
            <label className="label-field">Category (optional)</label>
            <select data-testid="submit-category" className="input-field" value={form.category} onChange={ch("category")}>
              <option value="">Let AI decide</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        <div>
          <label className="label-field">Phone (optional)</label>
          <input data-testid="submit-phone" className="input-field" value={form.customer_phone} onChange={ch("customer_phone")} placeholder="+91 98765 43210" />
        </div>

        <div>
          <label className="label-field">Complaint description</label>
          <textarea
            data-testid="submit-description"
            rows={9}
            className="input-field font-body"
            value={form.description}
            onChange={ch("description")}
            placeholder="Describe your issue. Include order numbers, dates, amounts, what happened, and what you expect."
            required minLength={10}
          />
          <div className="text-xs text-slate-400 mt-1">{form.description.length}/10000 characters</div>
        </div>

        <button type="submit" data-testid="submit-btn" disabled={loading} className="btn-primary">
          {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting</> : <><Send className="w-4 h-4" /> Submit complaint</>}
        </button>
      </form>
    </div>
  );
}
