import FinanceTracker from "./FinanceTracker";
import { useAuth } from "../auth/AuthContext";
import { Navigate } from "react-router-dom";

export default function ProtectedFinanceTracker() {
  const { token } = useAuth();

  if (!token) {
    return <Navigate to="/login" />;
  }

  return <FinanceTracker />;
}
