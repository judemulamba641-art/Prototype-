"""WAY User Frontend Store - Enterprise Grade"""
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { User, UserPreferences, ThemeConfig } from '@/types';

// Auth State
interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setAuth: (user: User, accessToken: string, refreshToken: string) => void;
  clearAuth: () => void;
  setAccessToken: (token: string) => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: true,
      setAuth: (user, accessToken, refreshToken) =>
        set({ user, accessToken, refreshToken, isAuthenticated: true, isLoading: false }),
      clearAuth: () =>
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false, isLoading: false }),
      setAccessToken: (token) => set({ accessToken: token }),
      setLoading: (loading) => set({ isLoading: loading }),
    }),
    {
      name: 'way-auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// UI State
interface UIState {
  sidebarOpen: boolean;
  theme: 'dark' | 'light' | 'system';
  notifications: number;
  isOffline: boolean;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setTheme: (theme: 'dark' | 'light' | 'system') => void;
  setNotifications: (count: number) => void;
  setOffline: (offline: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  theme: 'dark',
  notifications: 0,
  isOffline: !navigator.onLine,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setTheme: (theme) => set({ theme }),
  setNotifications: (count) => set({ notifications: count }),
  setOffline: (offline) => set({ isOffline: offline }),
}));

// Dashboard State
interface DashboardState {
  currentDashboard: string;
  widgets: Record<string, boolean>;
  layouts: Record<string, Record<string, unknown>>;
  setCurrentDashboard: (type: string) => void;
  toggleWidget: (widgetId: string) => void;
  saveLayout: (dashboardType: string, layout: Record<string, unknown>) => void;
}

export const useDashboardStore = create<DashboardState>()(
  persist(
    (set) => ({
      currentDashboard: 'user',
      widgets: {},
      layouts: {},
      setCurrentDashboard: (type) => set({ currentDashboard: type }),
      toggleWidget: (widgetId) =>
        set((state) => ({
          widgets: { ...state.widgets, [widgetId]: !state.widgets[widgetId] },
        })),
      saveLayout: (dashboardType, layout) =>
        set((state) => ({
          layouts: { ...state.layouts, [dashboardType]: layout },
        })),
    }),
    {
      name: 'way-dashboard-storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
);

// PWA State
interface PWAState {
  isInstalled: boolean;
  updateAvailable: boolean;
  deferredPrompt: any;
  setInstalled: (installed: boolean) => void;
  setUpdateAvailable: (available: boolean) => void;
  setDeferredPrompt: (prompt: any) => void;
}

export const usePWAStore = create<PWAState>((set) => ({
  isInstalled: false,
  updateAvailable: false,
  deferredPrompt: null,
  setInstalled: (installed) => set({ isInstalled: installed }),
  setUpdateAvailable: (available) => set({ updateAvailable: available }),
  setDeferredPrompt: (prompt) => set({ deferredPrompt: prompt }),
}));
