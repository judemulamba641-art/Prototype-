"""WAY User Frontend API Service - Enterprise Grade
Full backend connection with offline support, caching, and error handling
"""
import axios, { AxiosError, AxiosRequestConfig, AxiosResponse } from 'axios';
import { useAuthStore } from '@/store';
import { OfflineStorage } from './offlineStorage';

const API_BASE = '/api/user';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
});

// Request interceptor - add auth token and offline handling
api.interceptors.request.use(
  async (config) => {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Add request ID for tracing
    config.headers['X-Request-ID'] = crypto.randomUUID();

    // Check if offline and queue mutating requests
    if (!navigator.onLine && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(config.method?.toUpperCase() || '')) {
      await OfflineStorage.queueRequest(
        config.method || 'GET',
        config.url || '',
        config.data,
        config.headers as Record<string, string>
      );
      throw new Error('OFFLINE_REQUEST_QUEUED');
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle token refresh, caching, errors
api.interceptors.response.use(
  async (response) => {
    // Cache GET responses
    if (response.config.method?.toUpperCase() === 'GET' && response.status === 200) {
      const cacheKey = `${response.config.url}?${new URLSearchParams(response.config.params).toString()}`;
      await OfflineStorage.setCache(cacheKey, response.data, 60000); // 1 minute cache
    }
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // Try to serve from cache if offline
    if (!navigator.onLine && originalRequest.method?.toUpperCase() === 'GET') {
      const cacheKey = `${originalRequest.url}?${new URLSearchParams(originalRequest.params).toString()}`;
      const cached = await OfflineStorage.getCache(cacheKey);
      if (cached) {
        return { data: cached, status: 200, statusText: 'OK (Cached)', headers: {}, config: originalRequest } as AxiosResponse;
      }
    }

    // Token refresh on 401
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = useAuthStore.getState().refreshToken;

      if (refreshToken) {
        try {
          const res = await axios.post('/api/auth/refresh/', { refresh_token: refreshToken });
          const newToken = res.data.access_token;
          useAuthStore.getState().setAccessToken(newToken);

          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
          }
          return api(originalRequest);
        } catch {
          useAuthStore.getState().clearAuth();
          window.location.href = '/login';
        }
      }
    }

    // Rate limiting - retry with exponential backoff
    if (error.response?.status === 429) {
      const retryAfter = parseInt(error.response.headers['retry-after'] || '5');
      await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
      return api(originalRequest);
    }

    return Promise.reject(error);
  }
);

export default api;

// Auth Service
export const authService = {
  login: (email: string, password: string) =>
    axios.post('/api/auth/login/', { email, password }),
  register: (data: Record<string, unknown>) =>
    axios.post('/api/auth/register/', data),
  logout: () => axios.post('/api/auth/logout/'),
  refresh: (refreshToken: string) =>
    axios.post('/api/auth/refresh/', { refresh_token: refreshToken }),
  walletLogin: (walletAddress: string, message: string, signature: string, publicKey: string) =>
    axios.post('/api/auth/wallet_login/', { wallet_address: walletAddress, message, signature, public_key: publicKey }),
};

// Dashboard Service
export const dashboardService = {
  getDashboard: (type = 'user') => api.get(`/dashboard/me/?type=${type}`),
  getDeveloper: () => api.get('/dashboard/developer/'),
  getAdmin: () => api.get('/dashboard/admin/'),
  getOps: () => api.get('/dashboard/ops/'),
  getAuditor: () => api.get('/dashboard/auditor/'),
  getInvestor: () => api.get('/dashboard/investor/'),
  saveLayout: (type: string, layout: Record<string, unknown>) =>
    api.post('/dashboard/save_layout/', { type, layout }),
  getWidgets: (type: string) => api.get(`/dashboard/widgets/?type=${type}`),
};

// Profile Service
export const profileService = {
  getProfile: () => api.get('/profile/me/'),
  updateProfile: (data: Record<string, unknown>) =>
    api.patch('/profile/update_me/', data),
  getPreferences: () => api.get('/profile/preferences/'),
  updatePreferences: (data: Record<string, unknown>) =>
    api.post('/profile/update_preferences/', data),
  getTheme: () => api.get('/profile/theme/'),
  updateTheme: (data: Record<string, unknown>) =>
    api.post('/profile/update_theme/', data),
  getActivity: (days = 30) => api.get(`/profile/activity/?days=${days}`),
  getSecurity: () => api.get('/profile/security/'),
  getDevices: () => api.get('/profile/devices/'),
  revokeDevice: (deviceId: string) => api.post(`/profile/${deviceId}/revoke_device/`),
};

// Wallet Service
export const walletService = {
  getWallet: () => api.get('/wallet/me/'),
  getTransactions: (limit = 20, offset = 0) =>
    api.get(`/wallet/transactions/?limit=${limit}&offset=${offset}`),
  getPayments: (limit = 20, status?: string) =>
    api.get(`/wallet/payments/?limit=${limit}${status ? `&status=${status}` : ''}`),
  getTransfers: (limit = 20) => api.get(`/wallet/transfers/?limit=${limit}`),
  getBilling: (year?: number, month?: number) =>
    api.get(`/wallet/billing/${year ? `?year=${year}` : ''}${month ? `${year ? '&' : '?'}month=${month}` : ''}`),
};

// Credits Service
export const creditsService = {
  getCredits: () => api.get('/credits/me/'),
  getLedger: (limit = 50, offset = 0, type?: string) =>
    api.get(`/credits/ledger/?limit=${limit}&offset=${offset}${type ? `&type=${type}` : ''}`),
  getReserve: () => api.get('/credits/reserve/'),
  getTransfers: (limit = 50) => api.get(`/credits/transfers/?limit=${limit}`),
};

// Skills Service
export const skillsService = {
  getMySkills: () => api.get('/skills/me/'),
  getSummary: () => api.get('/skills/summary/'),
  getInstalled: () => api.get('/skills/installed/'),
  getExecutions: (limit = 20, status?: string) =>
    api.get(`/skills/executions/?limit=${limit}${status ? `&status=${status}` : ''}`),
  getSkillDetail: (id: string) => api.get(`/skills/${id}/detail/`),
  getDeveloperStats: () => api.get('/skills/developer_stats/'),
};

// Marketplace Service
export const marketplaceService = {
  listSkills: (params?: Record<string, string | number | undefined>) =>
    api.get('/marketplace/skills/', { params }),
  getReviews: (id: string, limit = 20, offset = 0) =>
    api.get(`/marketplace/${id}/reviews/?limit=${limit}&offset=${offset}`),
  getCategories: () => api.get('/marketplace/categories/'),
  getTrending: (limit = 10) => api.get(`/marketplace/trending/?limit=${limit}`),
  getFeatured: (limit = 6) => api.get(`/marketplace/featured/?limit=${limit}`),
};

// Notifications Service
export const notificationsService = {
  getNotifications: (unreadOnly = false, limit = 50, offset = 0, type?: string) =>
    api.get(`/notifications/me/?unread=${unreadOnly}&limit=${limit}&offset=${offset}${type ? `&type=${type}` : ''}`),
  getUnreadCount: () => api.get('/notifications/unread_count/'),
  markRead: (notificationId?: string) =>
    api.post('/notifications/mark_read/', { notification_id: notificationId }),
  getPreferences: () => api.get('/notifications/preferences/'),
  updatePreference: (type: string, channel: string, enabled: boolean) =>
    api.post('/notifications/update_preference/', { notification_type: type, channel, enabled }),
  getAlerts: (limit = 5) => api.get(`/notifications/alerts/?limit=${limit}`),
};

// Runtime Service
export const runtimeService = {
  getSessions: () => api.get('/runtime/sessions/'),
  getHistory: (limit = 50, offset = 0) => api.get(`/runtime/history/?limit=${limit}&offset=${offset}`),
  getSystemStatus: () => api.get('/runtime/system/'),
  getSandboxStats: () => api.get('/runtime/sandbox/'),
  getRegistry: () => api.get('/runtime/registry/'),
};

// Monitoring Service
export const monitoringService = {
  getDashboard: () => api.get('/monitoring/dashboard/'),
  getMetrics: (type?: string, window = '1m', limit = 100, startTime?: string, endTime?: string) =>
    api.get('/monitoring/metrics/', { params: { type, window, limit, start_time: startTime, end_time: endTime } }),
  getAudit: (params?: Record<string, string | number>) =>
    api.get('/monitoring/audit/', { params }),
  getEvents: (type?: string, processed?: boolean, limit = 50, offset = 0) =>
    api.get('/monitoring/events/', { params: { type, processed, limit, offset } }),
  verifyChain: (entityType?: string) =>
    api.get(`/monitoring/verify_chain/${entityType ? `?entity_type=${entityType}` : ''}`),
};

// Activity Service
export const activityService = {
  getActivity: (days = 30) => api.get(`/activity/me/?days=${days}`),
  getSearchHistory: (limit = 20) => api.get(`/activity/search_history/?limit=${limit}`),
};

// Search Service
export const searchService = {
  search: (query: string) => api.get(`/search/all/?q=${encodeURIComponent(query)}`),
};

// Navigation Service
export const navigationService = {
  getNavigation: () => api.get('/navigation/me/'),
};

// Analytics Service
export const analyticsService = {
  getGlobalStats: () => api.get('/analytics/global_stats/'),
  getUserGrowth: (days = 30) => api.get(`/analytics/user_growth/?days=${days}`),
  getRevenue: (days = 30) => api.get(`/analytics/revenue/?days=${days}`),
};
