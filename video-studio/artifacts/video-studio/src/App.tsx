import { type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';
import { useAuth } from "@workspace/replit-auth-web";

import { AppShell } from "@/components/layout/AppShell";
import LoginPage from "@/pages/auth/LoginPage";

import { PageLoading } from "@/components/shared";

// Pages
import DashboardPage from "@/pages/dashboard/DashboardPage";
import ProjectsPage from "@/pages/projects/ProjectsPage";
import ProjectDetailPage from "@/pages/projects/ProjectDetailPage";
import LibraryPage from "@/pages/library/LibraryPage";
import ScriptsPage from "@/pages/scripts/ScriptsPage";
import VoicesPage from "@/pages/voices/VoicesPage";
import JobsPage from "@/pages/jobs/JobsPage";
import SettingsPage from "@/pages/settings/SettingsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    }
  }
});

function ProtectedRoute({ component: Component }: { component: React.ComponentType }) {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) return <PageLoading />;
  if (!isAuthenticated) return <LoginPage />;
  
  return (
    <AppShell>
      <Component />
    </AppShell>
  );
}

function Router() {
  return (
    <RoutedErrorBoundary>
      <Switch>
        <Route path="/" component={() => <ProtectedRoute component={DashboardPage} />} />
        <Route path="/projects" component={() => <ProtectedRoute component={ProjectsPage} />} />
        <Route path="/projects/:id" component={() => <ProtectedRoute component={ProjectDetailPage} />} />
        <Route path="/library" component={() => <ProtectedRoute component={LibraryPage} />} />
        <Route path="/scripts" component={() => <ProtectedRoute component={ScriptsPage} />} />
        <Route path="/voices" component={() => <ProtectedRoute component={VoicesPage} />} />
        <Route path="/jobs" component={() => <ProtectedRoute component={JobsPage} />} />
        <Route path="/settings" component={() => <ProtectedRoute component={SettingsPage} />} />
        <Route component={NotFound} />
      </Switch>
    </RoutedErrorBoundary>
  );
}

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
