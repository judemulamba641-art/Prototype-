"""PWA Hook - Service Worker registration and offline support"""
import { useEffect, useState } from 'react';

interface PWAStatus {
  isInstalled: boolean;
  isOffline: boolean;
  canInstall: boolean;
  updateAvailable: boolean;
  registration: ServiceWorkerRegistration | null;
}

export function usePWA(): PWAStatus {
  const [status, setStatus] = useState<PWAStatus>({
    isInstalled: false,
    isOffline: !navigator.onLine,
    canInstall: false,
    updateAvailable: false,
    registration: null,
  });

  useEffect(() => {
    // Check if installed
    const isInstalled = window.matchMedia('(display-mode: standalone)').matches ||
                       (window.navigator as any).standalone === true;
    setStatus(prev => ({ ...prev, isInstalled }));

    // Online/offline detection
    const handleOnline = () => setStatus(prev => ({ ...prev, isOffline: false }));
    const handleOffline = () => setStatus(prev => ({ ...prev, isOffline: true }));

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Install prompt
    let deferredPrompt: any = null;
    const handleBeforeInstall = (e: Event) => {
      e.preventDefault();
      deferredPrompt = e;
      setStatus(prev => ({ ...prev, canInstall: true }));
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstall);

    // Service Worker registration
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.ready.then((registration) => {
        setStatus(prev => ({ ...prev, registration }));

        // Check for updates
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          if (newWorker) {
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                setStatus(prev => ({ ...prev, updateAvailable: true }));
              }
            });
          }
        });
      });
    }

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
    };
  }, []);

  return status;
}

export function installPWA(): Promise<boolean> {
  return new Promise((resolve) => {
    const prompt = (window as any).deferredPrompt;
    if (!prompt) {
      resolve(false);
      return;
    }
    prompt.prompt();
    prompt.userChoice.then((choiceResult: { outcome: string }) => {
      resolve(choiceResult.outcome === 'accepted');
    });
  });
}

export function updatePWA(): void {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready.then((registration) => {
      registration.update();
    });
  }
}
