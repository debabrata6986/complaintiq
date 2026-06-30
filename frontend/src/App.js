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
import SubmitComplaint from "@/pages/SubmitComplaint";
import ComplaintAnalysis from "@/pages/ComplaintAnalysis";
import ComplaintsList from "@/pages/ComplaintsList";
import KnowledgeBase from "@/pages/KnowledgeBase";
import AdminDashboard from "@/pages/AdminDashboard";
import Profile from "@/pages/Profile";

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
            <Route path="/submit" element={<SubmitComplaint />} />
            <Route path="/complaints" element={<ComplaintsList />} />
            <Route path="/complaints/:id" element={<ComplaintAnalysis />} />
            <Route path="/knowledge" element={<KnowledgeBase />} />
            <Route path="/admin" element={<ProtectedRoute roles={["admin","manager"]}><AdminDashboard /></ProtectedRoute>} />
            <Route path="/profile" element={<Profile />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
