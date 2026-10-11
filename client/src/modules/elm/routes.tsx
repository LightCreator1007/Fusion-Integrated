import { lazy } from "react";
import { Navigate, type RouteObject } from "react-router-dom";

/** One lazy chunk per page; the import() argument must be a static literal. */
const ApplyLeavePage = lazy(() => import("./pages/ApplyLeavePage"));
const MyLeavesPage = lazy(() => import("./pages/MyLeavesPage"));
const ApprovalsPage = lazy(() => import("./pages/ApprovalsPage"));
const RecordsPage = lazy(() => import("./pages/RecordsPage"));
const CalendarPage = lazy(() => import("./pages/CalendarPage"));
const PolicyPage = lazy(() => import("./pages/PolicyPage"));

/** Paths are RELATIVE to the manifest's basePath (/elm). Every entry has a
 *  matching nav item in the server's registry.py. */
export const routes: RouteObject[] = [
  { index: true, element: <Navigate to="mine" replace /> },
  { path: "apply", element: <ApplyLeavePage /> },
  { path: "mine", element: <MyLeavesPage /> },
  { path: "approvals", element: <ApprovalsPage /> },
  { path: "records", element: <RecordsPage /> },
  { path: "calendar", element: <CalendarPage /> },
  { path: "policy", element: <PolicyPage /> },
];
