import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './styles/global.css';

/**
 * Query defaults chosen for this app specifically:
 *
 * - `refetchOnWindowFocus: false` — graphs change only when a turn is sent, and
 *   a refetch on every tab switch would restart the force simulation, throwing
 *   away the layout the user had arranged.
 * - `retry: 1` — the common failure is "the server is not running", and
 *   retrying three times just delays a message the user needs immediately.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30_000,
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
