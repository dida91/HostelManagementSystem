/**
 * Client UI state: toasts, overlays, and per-viewer preferences.
 * Preferences persist in localStorage (guarded: it can be unavailable).
 */
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type ToastTone = "success" | "error" | "info";
export interface Toast {
  id: string;
  tone: ToastTone;
  title: string;
  description?: string;
}

interface UIState {
  toasts: Toast[];
  pushToast: (toast: Omit<Toast, "id">) => void;
  dismissToast: (id: string) => void;
  commandOpen: boolean;
  setCommandOpen: (open: boolean) => void;
  mobileNavOpen: boolean;
  setMobileNavOpen: (open: boolean) => void;
}

export const useUI = create<UIState>()((set) => ({
  toasts: [],
  pushToast: (toast) =>
    set((s) => ({
      toasts: [...s.toasts.slice(-3), { ...toast, id: Math.random().toString(36).slice(2) }],
    })),
  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  commandOpen: false,
  setCommandOpen: (commandOpen) => set({ commandOpen }),
  mobileNavOpen: false,
  setMobileNavOpen: (mobileNavOpen) => set({ mobileNavOpen }),
}));

/** Imperative toast API for mutation callbacks. */
export const toast = {
  success: (title: string, description?: string) =>
    useUI.getState().pushToast({ tone: "success", title, description }),
  error: (title: string, description?: string) =>
    useUI.getState().pushToast({ tone: "error", title, description }),
  info: (title: string, description?: string) =>
    useUI.getState().pushToast({ tone: "info", title, description }),
};

interface Prefs {
  reduceEffects: boolean;
  sidebarCollapsed: boolean;
  setReduceEffects: (value: boolean) => void;
  setSidebarCollapsed: (value: boolean) => void;
}

const safeStorage = createJSONStorage<Partial<Prefs>>(() => ({
  getItem: (key) => {
    try {
      return window.localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  setItem: (key, value) => {
    try {
      window.localStorage.setItem(key, value);
    } catch {
      /* private mode or blocked storage: preference lasts this visit only */
    }
  },
  removeItem: (key) => {
    try {
      window.localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
  },
}));

export const usePrefs = create<Prefs>()(
  persist(
    (set) => ({
      reduceEffects: false,
      sidebarCollapsed: false,
      setReduceEffects: (reduceEffects) => set({ reduceEffects }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
    }),
    {
      name: "kutumba-prefs",
      storage: safeStorage,
      // Rehydrated after mount (Providers) so server and first client render match.
      skipHydration: true,
      partialize: (s) => ({ reduceEffects: s.reduceEffects, sidebarCollapsed: s.sidebarCollapsed }),
    },
  ),
);
