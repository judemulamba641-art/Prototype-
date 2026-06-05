"""WAY User Frontend App - Enterprise Grade with PWA"""
import { RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { router } from '@/router';
import { usePWA } from '@/hooks';
import { useEffect } from 'react';
import { OfflineStorage } from '@/services/offlineStorage';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: (failureCount, error: any) => {
        // Don't retry on 401/403
        if (error?.response?.status === 401 || error?.response?.status === 403) {
          return false;
        }
        return failureCount < 3;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      refetchOnWindowFocus: false,
      networkMode: 'always', // Enable offline support
    },
    mutations: {
      retry: 1,
      networkMode: 'always',
    },
  },
});

function App() {
  const pwa = usePWA();

  useEffect(() => {
    // Process offline queue when coming back online
    const handleOnline = () => {
      OfflineStorage.processQueue();
    };
    window.addEventListener('online', handleOnline);
    return () => window.removeEventListener('online', handleOnline);
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <div className={`app ${pwa.isOffline ? 'offline-mode' : ''}`}>
        {pwa.isOffline && (
          <div className="offline-banner">
            <span className="offline-indicator">●</span>
            Offline Mode - Some features may be limited
          </div>
        )}
        <RouterProvider router={router} />
      </div>
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}

export default App;
