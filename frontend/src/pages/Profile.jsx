import { useAuth } from "@/context/AuthContext";
import { useNavigate } from "react-router-dom";
import { LogOut, User, Mail, Phone, Shield } from "lucide-react";

export default function Profile() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) return null;

  return (
    <div className="max-w-3xl" data-testid="profile-page">
      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">Account</div>
      <h1 className="font-heading text-3xl font-semibold text-slate-900">Your profile</h1>

      <div className="card-soft p-6 mt-6">
        <div className="flex items-center gap-4 mb-6 pb-6 border-b border-slate-100">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center text-white text-2xl font-medium">
            {user.full_name?.[0] || "U"}
          </div>
          <div>
            <h2 className="font-heading text-xl font-semibold text-slate-900" data-testid="profile-name">{user.full_name}</h2>
            <p className="text-sm text-slate-500 capitalize">{user.role}</p>
          </div>
        </div>

        <div className="space-y-4">
          <Field icon={Mail} label="Email" value={user.email} testid="profile-email" />
          <Field icon={Phone} label="Phone" value={user.phone || "Not provided"} testid="profile-phone" />
          <Field icon={Shield} label="Role" value={user.role} testid="profile-role" />
          <Field icon={User} label="Member since" value={new Date(user.created_at).toLocaleDateString()} testid="profile-created" />
        </div>

        <button onClick={() => { logout(); navigate("/login"); }} className="btn-primary mt-8 bg-red-600 hover:bg-red-700" data-testid="profile-logout">
          <LogOut className="w-4 h-4" /> Log out
        </button>
      </div>
    </div>
  );
}

function Field({ icon: Icon, label, value, testid }) {
  return (
    <div className="flex items-center gap-4 py-2" data-testid={testid}>
      <div className="w-9 h-9 rounded-[10px] bg-slate-50 text-slate-500 flex items-center justify-center"><Icon className="w-4 h-4" /></div>
      <div>
        <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold">{label}</div>
        <div className="text-sm text-slate-800 capitalize">{value}</div>
      </div>
    </div>
  );
}
