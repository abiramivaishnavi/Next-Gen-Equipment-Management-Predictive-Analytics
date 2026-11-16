import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import RequireAccess from "./auth/RequireAccess";
import Layout from "./components/Layout";

import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ComingSoonPage from "./pages/ComingSoonPage";
import RecordsPage from "./pages/RecordsPage";
import RecordsHubPage from "./pages/RecordsHubPage";

import RolesPage from "./pages/RolesPage";
import EmployeesPage from "./pages/EmployeesPage";
import ProjectsPage from "./pages/ProjectsPage";
import ProjectLookupPage from "./pages/ProjectLookupPage";
import InformationPage from "./pages/InformationPage";
import MaintenanceHistoryPage from "./pages/MaintenanceHistoryPage";
import OperationalPage from "./pages/OperationalPage";
import EquipmentPage from "./pages/EquipmentPage";
import TransfersPage from "./pages/TransfersPage";
import TransferApprovalsPage from "./pages/TransferApprovalsPage";
import ProjectActivitiesPage from "./pages/ProjectActivitiesPage";
import UtilizationLogsPage from "./pages/UtilizationLogsPage";
import FuelLogsPage from "./pages/FuelLogsPage";
import FuelRatesPage from "./pages/FuelRatesPage";
import IncidentsPage from "./pages/IncidentsPage";
import MaintenancePage from "./pages/MaintenancePage";
import BreakdownsPage from "./pages/BreakdownsPage";
import RepairsPage from "./pages/RepairsPage";

// Every signed-in page, in one list. Who may open each one is decided in src/menu.js.
const pages = [
  { path: "/", element: <DashboardPage /> },
  { path: "/equipment", element: <EquipmentPage /> },
  { path: "/fuel-logs", element: <FuelLogsPage /> },
  { path: "/fuel-rates", element: <FuelRatesPage /> },
  { path: "/utilization-logs", element: <UtilizationLogsPage /> },
  { path: "/project-activities", element: <ProjectActivitiesPage /> },
  { path: "/incidents", element: <IncidentsPage /> },
  { path: "/transfers", element: <TransfersPage /> },
  { path: "/transfer-approvals", element: <TransferApprovalsPage /> },
  { path: "/projects", element: <ProjectLookupPage /> },
  { path: "/manage-projects", element: <ProjectsPage /> },
  { path: "/maintenance", element: <MaintenancePage /> },
  { path: "/breakdowns", element: <BreakdownsPage /> },
  { path: "/repairs", element: <RepairsPage /> },
  { path: "/employees", element: <EmployeesPage /> },
  { path: "/roles", element: <RolesPage /> },
  { path: "/information", element: <InformationPage /> },
  { path: "/maintenance-history", element: <MaintenanceHistoryPage /> },
  { path: "/operational-data", element: <OperationalPage /> },
  { path: "/reports", element: <RecordsHubPage /> },
  { path: "/records/:key", element: <RecordsPage /> },
  { path: "/predictive-maintenance", element: <ComingSoonPage /> },
  { path: "/fuel-forecast", element: <ComingSoonPage /> },
];

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          {/* Everything else sits inside the layout (top bar + sidebar) and is access-checked. */}
          <Route element={<Layout />}>
            {pages.map((page) => (
              <Route
                key={page.path}
                path={page.path}
                element={<RequireAccess>{page.element}</RequireAccess>}
              />
            ))}
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
