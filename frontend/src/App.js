import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";
import { AuthProvider } from "@/context/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import AppLayout from "@/components/AppLayout";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import UnifiedSubmitPage from "@/pages/UnifiedSubmitPage";
import ComplaintAnalysis from "@/pages/ComplaintAnalysis";
import ComplaintsList from "@/pages/ComplaintsList";
import KnowledgeBase from "@/pages/KnowledgeBase";
import AdminDashboard from "@/pages/AdminDashboard";
import Profile from "@/pages/Profile";
// v4.0 Phase 1 — Multilingual
import MultilingualSubmitPanel from "@/features/multilingual/MultilingualSubmitPanel";
// v4.0 Phase 2 — Voice
import VoiceComplaintFlow from "@/features/voice/VoiceComplaintFlow";
// v4.0 Phase 5 — Multi-Modal Analysis
import MultiModalComplaintFlow from "@/features/multimodal/MultiModalComplaintFlow";
// v4.0 Phase 6 — Real-Time Customer Assistance
import RealtimeTestPage from "@/features/realtime/RealtimeTestPage";
// v4.0 Self-Healing Dashboard
import SelfHealingDashboard from "@/features/selfhealing/SelfHealingDashboard";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors closeButton />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/submit" element={<UnifiedSubmitPage />} />
            <Route path="/complaints" element={<ComplaintsList />} />
            <Route path="/complaints/:id" element={<ComplaintAnalysis />} />
            <Route path="/knowledge" element={<KnowledgeBase />} />
            <Route path="/admin" element={<ProtectedRoute roles={["admin","manager"]}><AdminDashboard /></ProtectedRoute>} />
            <Route path="/profile" element={<Profile />} />
            {/* v4.0 Phase 1 — Multilingual */}
            <Route path="/submit-multilingual" element={<MultilingualSubmitPanel />} />
            {/* v4.0 Phase 2 — Voice */}
            <Route path="/submit-voice" element={<VoiceComplaintFlow />} />
            {/* v4.0 Phase 5 — Multi-Modal Analysis */}
            <Route path="/submit-multimodal" element={<MultiModalComplaintFlow />} />
            {/* v4.0 Phase 6 — Real-Time Customer Assistance */}
            <Route path="/realtime-test" element={<RealtimeTestPage />} />
            {/* v4.0 Self-Healing Dashboard */}
            <Route path="/self-healing" element={<ProtectedRoute roles={["admin","manager"]}><SelfHealingDashboard /></ProtectedRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
