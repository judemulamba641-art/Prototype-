"""Offline Storage Service - IndexedDB for offline support"""
import { openDB, DBSchema, IDBPDatabase } from 'idb';

interface WAYDBSchema extends DBSchema {
  cache: {
    key: string;
    value: {
      data: unknown;
      timestamp: number;
      ttl: number;
    };
  };
  queue: {
    key: number;
    value: {
      id: number;
      method: string;
      url: string;
      data: unknown;
      headers: Record<string, string>;
      timestamp: number;
      retries: number;
    };
  };
  user: {
    key: string;
    value: unknown;
  };
}

const DB_NAME = 'way-offline-db';
const DB_VERSION = 1;

let dbPromise: Promise<IDBPDatabase<WAYDBSchema>> | null = null;

function getDB(): Promise<IDBPDatabase<WAYDBSchema>> {
  if (!dbPromise) {
    dbPromise = openDB<WAYDBSchema>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains('cache')) {
          db.createObjectStore('cache');
        }
        if (!db.objectStoreNames.contains('queue')) {
          db.createObjectStore('queue', { keyPath: 'id', autoIncrement: true });
        }
        if (!db.objectStoreNames.contains('user')) {
          db.createObjectStore('user');
        }
      },
    });
  }
  return dbPromise;
}

export const OfflineStorage = {
  // Cache operations
  async setCache(key: string, data: unknown, ttl: number = 300000): Promise<void> {
    const db = await getDB();
    await db.put('cache', {
      data,
      timestamp: Date.now(),
      ttl,
    }, key);
  },

  async getCache<T>(key: string): Promise<T | null> {
    const db = await getDB();
    const entry = await db.get('cache', key);
    if (!entry) return null;

    if (Date.now() - entry.timestamp > entry.ttl) {
      await db.delete('cache', key);
      return null;
    }

    return entry.data as T;
  },

  async deleteCache(key: string): Promise<void> {
    const db = await getDB();
    await db.delete('cache', key);
  },

  async clearCache(): Promise<void> {
    const db = await getDB();
    await db.clear('cache');
  },

  // Request queue for offline support
  async queueRequest(
    method: string,
    url: string,
    data: unknown,
    headers: Record<string, string> = {}
  ): Promise<number> {
    const db = await getDB();
    return await db.add('queue', {
      method,
      url,
      data,
      headers,
      timestamp: Date.now(),
      retries: 0,
    });
  },

  async getQueuedRequests(): Promise<WAYDBSchema['queue']['value'][]> {
    const db = await getDB();
    return await db.getAll('queue');
  },

  async removeQueuedRequest(id: number): Promise<void> {
    const db = await getDB();
    await db.delete('queue', id);
  },

  async processQueue(): Promise<void> {
    const requests = await this.getQueuedRequests();
    for (const req of requests) {
      try {
        const response = await fetch(req.url, {
          method: req.method,
          headers: req.headers,
          body: req.data ? JSON.stringify(req.data) : undefined,
        });
        if (response.ok) {
          await this.removeQueuedRequest(req.id);
        } else {
          throw new Error(`HTTP ${response.status}`);
        }
      } catch (error) {
        if (req.retries >= 3) {
          await this.removeQueuedRequest(req.id);
        } else {
          const db = await getDB();
          await db.put('queue', { ...req, retries: req.retries + 1 });
        }
      }
    }
  },

  // User data persistence
  async setUserData(key: string, data: unknown): Promise<void> {
    const db = await getDB();
    await db.put('user', data, key);
  },

  async getUserData<T>(key: string): Promise<T | null> {
    const db = await getDB();
    return await db.get('user', key) as T | null;
  },
};
