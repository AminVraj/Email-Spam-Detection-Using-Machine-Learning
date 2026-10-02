import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppLayout } from "./layouts/AppLayout";
import { Dashboard } from "./pages/Dashboard";
import { Inbox } from "./pages/Inbox";
import { Analytics } from "./pages/Analytics";
import { AdaptiveLearning } from "./pages/AdaptiveLearning";
import { ModelManagement } from "./pages/ModelManagement";
import { AnalyzeEmail } from "./pages/AnalyzeEmail";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="inbox" element={<Inbox />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="adaptive" element={<AdaptiveLearning />} />
            <Route path="models" element={<ModelManagement />} />
            <Route path="analyze" element={<AnalyzeEmail />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
