import React, { useState } from "react";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Backtest } from "./pages/Backtest";
import { Alerts } from "./pages/Alerts";

export default function App() {
  const [page, setPage] = useState("dashboard");

  return (
    <Layout active={page} onNavigate={setPage}>
      {page === "dashboard" && <Dashboard />}
      {page === "backtest" && <Backtest />}
      {page === "alerts" && <Alerts />}
    </Layout>
  );
}
