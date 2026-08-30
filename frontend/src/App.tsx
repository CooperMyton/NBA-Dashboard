import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import ModelLab from "./pages/ModelLab";
import Players from "./pages/Players";
import PredictionTracker from "./pages/PredictionTracker";
import SeasonProjection from "./pages/SeasonProjection";
import TeamDetail from "./pages/TeamDetail";
import Teams from "./pages/Teams";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: 1, refetchOnWindowFocus: false } },
});

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "teams", element: <Teams /> },
      { path: "teams/:id", element: <TeamDetail /> },
      { path: "players", element: <Players /> },
      { path: "model-lab", element: <ModelLab /> },
      { path: "predictions", element: <PredictionTracker /> },
      { path: "projection", element: <SeasonProjection /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
