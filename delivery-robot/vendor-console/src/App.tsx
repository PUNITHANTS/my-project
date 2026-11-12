import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { login as apiLogin, logout as apiLogout } from "./api/auth";
import { isLoggedIn } from "./api/client";
import { DEFAULT_VENDOR_SETTINGS } from "./data/defaults";
import { useOrders } from "./hooks/useOrders";
import { useVendor } from "./hooks/useVendor";
import AuthPage from "./pages/AuthPage";
import DashboardPage from "./pages/DashboardPage";
import MenuPage from "./pages/MenuPage";
import OrderHistoryPage from "./pages/OrderHistoryPage";
import SettingsPage from "./pages/SettingsPage";
import type { VendorSettings } from "./types";

type PageKey = "dashboard" | "history" | "menu" | "settings";

/** @deprecated Per-vendor keys are used; kept only for one-time migration. */
const LEGACY_SETTINGS_KEY = "vendor_console_settings";

function settingsStorageKey(vendorId: number): string {
  return `vendor_console_settings_v${vendorId}`;
}

function readJson<T>(key: string, fallback: T): T {
  const raw = localStorage.getItem(key);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

/** Merge saved UI prefs with server-backed vendor + manager profile (fixes stale demo defaults in localStorage). */
function mergeStoredSettingsWithProfile(
  stored: VendorSettings | null,
  vendorName: string,
  managerEmail: string,
  managerPhone: string,
): VendorSettings {
  const merged: VendorSettings = {
    ...DEFAULT_VENDOR_SETTINGS,
    ...(stored ?? {}),
    businessName: vendorName.trim() || DEFAULT_VENDOR_SETTINGS.businessName,
  };

  const emailTrim = managerEmail.trim();
  const phoneTrim = managerPhone.trim();

  if (emailTrim) {
    merged.contactEmail = emailTrim;
  } else if (merged.contactEmail === DEFAULT_VENDOR_SETTINGS.contactEmail) {
    merged.contactEmail = "";
  }

  if (phoneTrim) {
    merged.contactPhone = phoneTrim;
  } else if (merged.contactPhone === DEFAULT_VENDOR_SETTINGS.contactPhone) {
    merged.contactPhone = "";
  }

  return merged;
}

export default function App() {
  const [activePage, setActivePage] = useState<PageKey>("dashboard");
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(() => isLoggedIn());
  const [settings, setSettings] = useState<VendorSettings>(DEFAULT_VENDOR_SETTINGS);
  const skipNextSettingsPersistRef = useRef(false);

  const {
    vendorId,
    vendorName,
    managerEmail,
    managerPhone,
    isLoading: vendorProfileLoading,
    isPaused,
    togglePause,
    updateVendorName,
  } = useVendor(isAuthenticated);

  const headerVendorLabel =
    vendorName || (vendorProfileLoading ? "…" : "Vendor");

  const {
    allOrders,
    newOrders,
    acceptedOrders,
    preparingOrders,
    readyOrders,
    dispatchedOrders,
    isLoading: ordersLoading,
    error: ordersError,
    newOrderIds,
    updateOrderStatus,
  } = useOrders({ autoAcceptOrders: settings.autoAcceptOrders, vendorId });

  useLayoutEffect(() => {
    if (!isAuthenticated || vendorId == null) return;
    skipNextSettingsPersistRef.current = true;
    const key = settingsStorageKey(vendorId);
    let stored = readJson<VendorSettings | null>(key, null);
    if (!stored) {
      const legacy = readJson<VendorSettings | null>(LEGACY_SETTINGS_KEY, null);
      if (legacy) {
        stored = legacy;
        try {
          localStorage.setItem(key, JSON.stringify(legacy));
          localStorage.removeItem(LEGACY_SETTINGS_KEY);
        } catch {
          /* ignore quota errors */
        }
      }
    }
    setSettings(
      mergeStoredSettingsWithProfile(stored, vendorName, managerEmail, managerPhone),
    );
  }, [isAuthenticated, vendorId, vendorName, managerEmail, managerPhone]);

  useEffect(() => {
    if (!isAuthenticated || vendorId == null) return;
    if (skipNextSettingsPersistRef.current) {
      skipNextSettingsPersistRef.current = false;
      return;
    }
    try {
      localStorage.setItem(settingsStorageKey(vendorId), JSON.stringify(settings));
    } catch {
      /* ignore */
    }
  }, [settings, vendorId, isAuthenticated]);

  const shellClasses = useMemo(() => {
    if (settings.theme === "light") {
      return "h-screen bg-zinc-100 text-zinc-900";
    }
    return "h-screen bg-zinc-950 text-zinc-100";
  }, [settings.theme]);
  const isLight = settings.theme === "light";

  // Listen for session expiry fired by the axios interceptor when refresh fails.
  useEffect(() => {
    function onSessionExpired() {
      setIsAuthenticated(false);
      setActivePage("dashboard");
    }
    window.addEventListener("vendor:session-expired", onSessionExpired);
    return () => window.removeEventListener("vendor:session-expired", onSessionExpired);
  }, []);

  async function login(username: string, password: string): Promise<boolean> {
    const ok = await apiLogin(username, password);
    if (ok) setIsAuthenticated(true);
    return ok;
  }

  function logout() {
    apiLogout();
    setIsAuthenticated(false);
    setActivePage("dashboard");
  }

  async function handleSettingsSave(next: VendorSettings) {
    setSettings(next);
    // Sync business name to backend if it changed
    if (next.businessName !== settings.businessName) {
      await updateVendorName(next.businessName);
    }
  }

  if (!isAuthenticated) {
    return <AuthPage onLogin={login} />;
  }

  return (
    <div className={`${shellClasses} flex flex-col font-sans`}>
      <header className={`grid grid-cols-3 items-center px-5 h-13 border-b shrink-0 relative ${isLight ? "border-zinc-300 bg-white text-zinc-900" : "border-zinc-800 bg-zinc-900 text-zinc-100"}`}>
        <button
          type="button"
          onClick={() => setIsMenuOpen(true)}
          aria-label="Open navigation menu"
          className="flex items-center justify-start gap-2.5 min-w-0 -ml-1 p-1 -my-1 rounded-md hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/60"
        >
          <span className="shrink-0 text-current" aria-hidden>
            <svg
              className="w-6 h-6"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <path d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </span>
          <span className="font-mono text-[18px] font-bold tracking-wide truncate">
            {headerVendorLabel}
          </span>
        </button>
        <div className="flex items-center justify-center">
          <span className={`text-xs ${isLight ? "text-zinc-600" : "text-zinc-400"}`}>
            {settings.isStoreOpen ? "Store Open" : "Store Closed"}
          </span>
        </div>
        <div className="flex justify-end items-center gap-2">
          <button onClick={logout} className={`px-3 py-1.5 rounded border text-xs ${isLight ? "border-zinc-300 text-zinc-700 hover:bg-zinc-100" : "border-zinc-700 text-zinc-300 hover:bg-zinc-800"}`}>
            Logout
          </button>
        </div>
      </header>

      {isMenuOpen && (
        <>
          <button
            aria-label="Close navigation"
            onClick={() => setIsMenuOpen(false)}
            className="fixed inset-0 bg-black/40 z-20"
          />
          <aside
            className={`fixed left-0 top-0 h-full w-72 z-30 border-r p-4 ${isLight ? "bg-white border-zinc-300 text-zinc-900" : "bg-zinc-900 border-zinc-700 text-zinc-100"}`}
          >
            <div className="flex items-center justify-between mb-4">
              <span className="font-mono text-lg font-bold tracking-wide">{headerVendorLabel}</span>
              <button
                onClick={() => setIsMenuOpen(false)}
                className={`px-2 py-1 rounded text-sm ${isLight ? "hover:bg-zinc-100" : "hover:bg-zinc-800"}`}
              >
                ✕
              </button>
            </div>
            <div className="flex flex-col gap-2">
              {[
                { key: "dashboard", label: "Dashboard" },
                { key: "history", label: "Order History" },
                { key: "menu", label: "Menu" },
                { key: "settings", label: "Settings" },
              ].map((item) => (
                <button
                  key={item.key}
                  onClick={() => {
                    setActivePage(item.key as PageKey);
                    setIsMenuOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2 rounded text-sm border ${
                    activePage === item.key
                      ? isLight
                        ? "bg-zinc-100 border-zinc-300"
                        : "bg-zinc-800 border-zinc-700"
                      : isLight
                        ? "border-zinc-200 hover:bg-zinc-100"
                        : "border-zinc-800 hover:bg-zinc-800"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </aside>
        </>
      )}

      <div className="flex-1 min-h-0">
        {activePage === "dashboard" && (
          <DashboardPage
            newOrders={newOrders}
            acceptedOrders={acceptedOrders}
            preparingOrders={preparingOrders}
            readyOrders={readyOrders}
            dispatchedOrders={dispatchedOrders}
            isPaused={isPaused}
            isLight={isLight}
            newOrderIds={newOrderIds}
            isLoading={ordersLoading}
            error={ordersError}
            onTogglePause={togglePause}
            onUpdateStatus={updateOrderStatus}
          />
        )}
        {activePage === "history" && <OrderHistoryPage orders={allOrders} isLight={isLight} />}
        {activePage === "menu" && <MenuPage isLight={isLight} vendorId={vendorId} />}
        {activePage === "settings" && <SettingsPage value={settings} isLight={isLight} onChange={handleSettingsSave} />}
      </div>
    </div>
  );
}
