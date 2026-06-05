"""WAY User Frontend Hooks - Enterprise Grade
All hooks connected to backend with caching, offline support, and real-time updates
"""
import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query';
import { useEffect, useCallback } from 'react';
import {
  authService,
  dashboardService,
  profileService,
  walletService,
  creditsService,
  skillsService,
  marketplaceService,
  notificationsService,
  runtimeService,
  monitoringService,
  activityService,
  searchService,
  navigationService,
  analyticsService,
} from '@/services';
import { useAuthStore, useUIStore } from '@/store';
import { usePWA } from './usePWA';
import { OfflineStorage } from '@/services/offlineStorage';

// ==================== AUTH HOOKS ====================
export const useLogin = () => {
  const { setAuth } = useAuthStore();
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      authService.login(email, password),
    onSuccess: (res) => {
      setAuth(res.data.user, res.data.access_token, res.data.refresh_token);
      // Persist user data for offline
      OfflineStorage.setUserData('user', res.data.user);
      qc.invalidateQueries();
    },
  });
};

export const useRegister = () => {
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => authService.register(data),
  });
};

export const useLogout = () => {
  const { clearAuth } = useAuthStore();
  const qc = useQueryClient();

  return useMutation({
    mutationFn: () => authService.logout(),
    onSuccess: () => {
      clearAuth();
      OfflineStorage.clearCache();
      qc.clear();
    },
  });
};

// ==================== DASHBOARD HOOKS ====================
export const useDashboard = (type = 'user') => {
  return useQuery({
    queryKey: ['dashboard', type],
    queryFn: () => dashboardService.getDashboard(type).then((r) => r.data),
    refetchInterval: 30000,
    staleTime: 15000,
  });
};

export const useSaveLayout = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ type, layout }: { type: string; layout: Record<string, unknown> }) =>
      dashboardService.saveLayout(type, layout).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboard'] }),
  });
};

// ==================== PROFILE HOOKS ====================
export const useProfile = () => {
  return useQuery({
    queryKey: ['profile'],
    queryFn: () => profileService.getProfile().then((r) => r.data),
    staleTime: 60000,
  });
};

export const useUpdateProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      profileService.updateProfile(data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
};

export const usePreferences = () => {
  return useQuery({
    queryKey: ['preferences'],
    queryFn: () => profileService.getPreferences().then((r) => r.data),
  });
};

export const useUpdatePreferences = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      profileService.updatePreferences(data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['preferences'] }),
  });
};

export const useTheme = () => {
  return useQuery({
    queryKey: ['theme'],
    queryFn: () => profileService.getTheme().then((r) => r.data),
  });
};

export const useActivity = (days = 30) => {
  return useQuery({
    queryKey: ['activity', days],
    queryFn: () => profileService.getActivity(days).then((r) => r.data),
  });
};

export const useSecurity = () => {
  return useQuery({
    queryKey: ['security'],
    queryFn: () => profileService.getSecurity().then((r) => r.data),
  });
};

export const useDevices = () => {
  return useQuery({
    queryKey: ['devices'],
    queryFn: () => profileService.getDevices().then((r) => r.data),
  });
};

export const useRevokeDevice = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (deviceId: string) => profileService.revokeDevice(deviceId).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['devices'] }),
  });
};

// ==================== WALLET HOOKS ====================
export const useWallet = () => {
  return useQuery({
    queryKey: ['wallet'],
    queryFn: () => walletService.getWallet().then((r) => r.data),
    refetchInterval: 15000,
    staleTime: 10000,
  });
};

export const useTransactions = (limit = 20) => {
  return useInfiniteQuery({
    queryKey: ['transactions', limit],
    queryFn: ({ pageParam = 0 }) =>
      walletService.getTransactions(limit, pageParam).then((r) => r.data),
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.offset + lastPage.limit : undefined,
    initialPageParam: 0,
  });
};

export const usePayments = (limit = 20, status?: string) => {
  return useQuery({
    queryKey: ['payments', limit, status],
    queryFn: () => walletService.getPayments(limit, status).then((r) => r.data),
  });
};

export const useBilling = (year?: number, month?: number) => {
  return useQuery({
    queryKey: ['billing', year, month],
    queryFn: () => walletService.getBilling(year, month).then((r) => r.data),
  });
};

// ==================== CREDITS HOOKS ====================
export const useCredits = () => {
  return useQuery({
    queryKey: ['credits'],
    queryFn: () => creditsService.getCredits().then((r) => r.data),
    refetchInterval: 15000,
    staleTime: 10000,
  });
};

export const useLedger = (limit = 50, type?: string) => {
  return useInfiniteQuery({
    queryKey: ['ledger', limit, type],
    queryFn: ({ pageParam = 0 }) =>
      creditsService.getLedger(limit, pageParam, type).then((r) => r.data),
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.offset + lastPage.limit : undefined,
    initialPageParam: 0,
  });
};

export const useReserve = () => {
  return useQuery({
    queryKey: ['reserve'],
    queryFn: () => creditsService.getReserve().then((r) => r.data),
  });
};

// ==================== SKILLS HOOKS ====================
export const useMySkills = () => {
  return useQuery({
    queryKey: ['my-skills'],
    queryFn: () => skillsService.getMySkills().then((r) => r.data),
  });
};

export const useSkillsSummary = () => {
  return useQuery({
    queryKey: ['skills-summary'],
    queryFn: () => skillsService.getSummary().then((r) => r.data),
  });
};

export const useInstalledSkills = () => {
  return useQuery({
    queryKey: ['installed-skills'],
    queryFn: () => skillsService.getInstalled().then((r) => r.data),
  });
};

export const useSkillExecutions = (limit = 20, status?: string) => {
  return useQuery({
    queryKey: ['skill-executions', limit, status],
    queryFn: () => skillsService.getExecutions(limit, status).then((r) => r.data),
  });
};

export const useSkillDetail = (id: string) => {
  return useQuery({
    queryKey: ['skill-detail', id],
    queryFn: () => skillsService.getSkillDetail(id).then((r) => r.data),
    enabled: !!id,
  });
};

export const useDeveloperStats = () => {
  return useQuery({
    queryKey: ['developer-stats'],
    queryFn: () => skillsService.getDeveloperStats().then((r) => r.data),
  });
};

// ==================== MARKETPLACE HOOKS ====================
export const useMarketplaceSkills = (params?: Record<string, string | number | undefined>) => {
  return useInfiniteQuery({
    queryKey: ['marketplace-skills', params],
    queryFn: ({ pageParam = 0 }) =>
      marketplaceService.listSkills({ ...params, offset: pageParam }).then((r) => r.data),
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.offset + lastPage.limit : undefined,
    initialPageParam: 0,
  });
};

export const useSkillReviews = (id: string, limit = 20) => {
  return useQuery({
    queryKey: ['skill-reviews', id, limit],
    queryFn: () => marketplaceService.getReviews(id, limit).then((r) => r.data),
    enabled: !!id,
  });
};

export const useCategories = () => {
  return useQuery({
    queryKey: ['categories'],
    queryFn: () => marketplaceService.getCategories().then((r) => r.data),
  });
};

export const useTrending = (limit = 10) => {
  return useQuery({
    queryKey: ['trending', limit],
    queryFn: () => marketplaceService.getTrending(limit).then((r) => r.data),
  });
};

export const useFeatured = (limit = 6) => {
  return useQuery({
    queryKey: ['featured', limit],
    queryFn: () => marketplaceService.getFeatured(limit).then((r) => r.data),
  });
};

// ==================== NOTIFICATIONS HOOKS ====================
export const useNotifications = (unreadOnly = false, limit = 50, type?: string) => {
  const { setNotifications } = useUIStore();

  return useQuery({
    queryKey: ['notifications', unreadOnly, limit, type],
    queryFn: () => notificationsService.getNotifications(unreadOnly, limit, 0, type).then((r) => r.data),
    onSuccess: (data) => {
      if (unreadOnly) setNotifications(data.unread);
    },
    refetchInterval: 10000,
  });
};

export const useUnreadCount = () => {
  const { setNotifications } = useUIStore();

  return useQuery({
    queryKey: ['unread-count'],
    queryFn: () => notificationsService.getUnreadCount().then((r) => r.data.count),
    onSuccess: (count) => setNotifications(count),
    refetchInterval: 10000,
  });
};

export const useMarkRead = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (notificationId?: string) =>
      notificationsService.markRead(notificationId).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] });
      qc.invalidateQueries({ queryKey: ['unread-count'] });
    },
  });
};

export const useNotificationPreferences = () => {
  return useQuery({
    queryKey: ['notification-preferences'],
    queryFn: () => notificationsService.getPreferences().then((r) => r.data),
  });
};

export const useUpdateNotificationPreference = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ type, channel, enabled }: { type: string; channel: string; enabled: boolean }) =>
      notificationsService.updatePreference(type, channel, enabled).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notification-preferences'] }),
  });
};

// ==================== RUNTIME HOOKS ====================
export const useActiveSessions = () => {
  return useQuery({
    queryKey: ['active-sessions'],
    queryFn: () => runtimeService.getSessions().then((r) => r.data),
    refetchInterval: 5000,
  });
};

export const useSystemStatus = () => {
  return useQuery({
    queryKey: ['system-status'],
    queryFn: () => runtimeService.getSystemStatus().then((r) => r.data),
    refetchInterval: 10000,
  });
};

export const useSandboxStats = () => {
  return useQuery({
    queryKey: ['sandbox-stats'],
    queryFn: () => runtimeService.getSandboxStats().then((r) => r.data),
  });
};

export const useRegistry = () => {
  return useQuery({
    queryKey: ['registry'],
    queryFn: () => runtimeService.getRegistry().then((r) => r.data),
  });
};

// ==================== MONITORING HOOKS ====================
export const useMonitoringDashboard = () => {
  return useQuery({
    queryKey: ['monitoring-dashboard'],
    queryFn: () => monitoringService.getDashboard().then((r) => r.data),
    refetchInterval: 15000,
    enabled: false,
  });
};

export const useMetrics = (type?: string, window = '1m', limit = 100) => {
  return useQuery({
    queryKey: ['metrics', type, window, limit],
    queryFn: () => monitoringService.getMetrics(type, window, limit).then((r) => r.data),
    enabled: false,
  });
};

export const useAuditLogs = (params?: Record<string, string | number>) => {
  return useQuery({
    queryKey: ['audit-logs', params],
    queryFn: () => monitoringService.getAudit(params).then((r) => r.data),
    enabled: false,
  });
};

// ==================== WEBSOCKET HOOK ====================
export const useWebSocket = (channel: string, onMessage: (data: unknown) => void) => {
  const { accessToken } = useAuthStore();

  useEffect(() => {
    if (!accessToken) return;

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/user/${channel}/?token=${accessToken}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`WebSocket connected: ${channel}`);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (e) {
        console.error('WebSocket message parse error:', e);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log(`WebSocket disconnected: ${channel}`);
    };

    return () => {
      ws.close();
    };
  }, [channel, accessToken, onMessage]);
};

// ==================== SEARCH HOOK ====================
export const useSearch = (query: string) => {
  return useQuery({
    queryKey: ['search', query],
    queryFn: () => searchService.search(query).then((r) => r.data),
    enabled: query.length >= 2,
    staleTime: 60000,
  });
};

// ==================== NAVIGATION HOOK ====================
export const useNavigation = () => {
  return useQuery({
    queryKey: ['navigation'],
    queryFn: () => navigationService.getNavigation().then((r) => r.data),
  });
};

// ==================== ANALYTICS HOOKS ====================
export const useGlobalStats = () => {
  return useQuery({
    queryKey: ['global-stats'],
    queryFn: () => analyticsService.getGlobalStats().then((r) => r.data),
    enabled: false,
  });
};

export const useUserGrowth = (days = 30) => {
  return useQuery({
    queryKey: ['user-growth', days],
    queryFn: () => analyticsService.getUserGrowth(days).then((r) => r.data),
    enabled: false,
  });
};

export const useRevenue = (days = 30) => {
  return useQuery({
    queryKey: ['revenue', days],
    queryFn: () => analyticsService.getRevenue(days).then((r) => r.data),
    enabled: false,
  });
};

export { usePWA };
