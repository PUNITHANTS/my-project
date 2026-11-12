import { useEffect, useState, type ReactNode } from "react";
import type { VendorSettings } from "../types";

interface SettingsPageProps {
  value: VendorSettings;
  isLight?: boolean;
  onChange: (next: VendorSettings) => void;
}

export default function SettingsPage({ value, isLight = false, onChange }: SettingsPageProps) {
  const [local, setLocal] = useState(value);
  const [savedAt, setSavedAt] = useState<string>("");
  const [editing, setEditing] = useState<keyof VendorSettings | null>(null);

  useEffect(() => {
    setLocal(value);
  }, [value]);

  function update<K extends keyof VendorSettings>(key: K, next: VendorSettings[K]) {
    setLocal((prev) => ({ ...prev, [key]: next }));
  }

  function save() {
    onChange(local);
    setSavedAt(new Date().toLocaleTimeString());
    setEditing(null);
  }

  function renderField<K extends keyof VendorSettings>(
    key: K,
    label: string,
    input: ReactNode
  ) {
    const isEditing = editing === key;
    return (
      <div className={`border rounded p-3 ${isLight ? "border-zinc-300 bg-white" : "border-zinc-700 bg-zinc-900"}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <p className={`text-xs mb-1 ${isLight ? "text-zinc-600" : "text-zinc-400"}`}>{label}</p>
            {isEditing ? (
              input
            ) : (
              <p className="text-sm break-words">
                {typeof local[key] === "boolean"
                  ? local[key]
                    ? "Enabled"
                    : "Disabled"
                  : String(local[key])}
              </p>
            )}
          </div>
          <button
            onClick={() => setEditing(isEditing ? null : key)}
            className={`px-2 py-1 rounded border text-xs ${isLight ? "border-zinc-300 hover:bg-zinc-100" : "border-zinc-600 hover:bg-zinc-800"}`}
            title="Edit"
          >
            ✎
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-5 space-y-5 overflow-y-auto h-full">
      <h2 className="font-mono text-lg font-semibold">Vendor Settings</h2>

      <section className="grid md:grid-cols-2 gap-4">
        {renderField(
          "businessName",
          "Business name",
          <input className={`w-full px-3 py-2 rounded border ${isLight ? "bg-white border-zinc-300" : "bg-zinc-800 border-zinc-700"}`} value={local.businessName} onChange={(e) => update("businessName", e.target.value)} />
        )}
        {renderField(
          "contactEmail",
          "Contact email",
          <input className={`w-full px-3 py-2 rounded border ${isLight ? "bg-white border-zinc-300" : "bg-zinc-800 border-zinc-700"}`} value={local.contactEmail} onChange={(e) => update("contactEmail", e.target.value)} />
        )}
        {renderField(
          "contactPhone",
          "Contact phone",
          <input className={`w-full px-3 py-2 rounded border ${isLight ? "bg-white border-zinc-300" : "bg-zinc-800 border-zinc-700"}`} value={local.contactPhone} onChange={(e) => update("contactPhone", e.target.value)} />
        )}
        {renderField(
          "pickupPrepTimeMins",
          "Pickup prep time (mins)",
          <input type="number" min={1} className={`w-full px-3 py-2 rounded border ${isLight ? "bg-white border-zinc-300" : "bg-zinc-800 border-zinc-700"}`} value={local.pickupPrepTimeMins} onChange={(e) => update("pickupPrepTimeMins", Number(e.target.value) || 1)} />
        )}
        {renderField(
          "hoursOfOperation",
          "Hours of operation",
          <input className={`w-full px-3 py-2 rounded border ${isLight ? "bg-white border-zinc-300" : "bg-zinc-800 border-zinc-700"}`} value={local.hoursOfOperation} onChange={(e) => update("hoursOfOperation", e.target.value)} />
        )}
        {renderField(
          "isStoreOpen",
          "Store open",
          <label className="inline-flex items-center gap-2 text-sm">
            <input type="checkbox" checked={local.isStoreOpen} onChange={(e) => update("isStoreOpen", e.target.checked)} />
            {local.isStoreOpen ? "Open" : "Closed"}
          </label>
        )}
        {renderField(
          "autoAcceptOrders",
          "Auto-accept orders",
          <label className="inline-flex items-center gap-2 text-sm">
            <input type="checkbox" checked={local.autoAcceptOrders} onChange={(e) => update("autoAcceptOrders", e.target.checked)} />
            {local.autoAcceptOrders ? "Enabled" : "Disabled"}
          </label>
        )}
        {renderField(
          "theme",
          "Theme",
          <select className={`w-full px-3 py-2 rounded border ${isLight ? "bg-white border-zinc-300" : "bg-zinc-800 border-zinc-700"}`} value={local.theme} onChange={(e) => update("theme", e.target.value as VendorSettings["theme"])}>
            <option value="dark">Dark</option>
            <option value="light">Light</option>
          </select>
        )}
        {renderField(
          "language",
          "Language",
          <select className={`w-full px-3 py-2 rounded border ${isLight ? "bg-white border-zinc-300" : "bg-zinc-800 border-zinc-700"}`} value={local.language} onChange={(e) => update("language", e.target.value as VendorSettings["language"])}>
            <option value="en">English</option>
            <option value="es">Spanish</option>
          </select>
        )}
        {renderField(
          "passwordHint",
          "Change password (placeholder)",
          <input type="password" className={`w-full px-3 py-2 rounded border ${isLight ? "bg-white border-zinc-300" : "bg-zinc-800 border-zinc-700"}`} value={local.passwordHint} onChange={(e) => update("passwordHint", e.target.value)} />
        )}
        {renderField(
          "twoFactorEnabled",
          "2FA (placeholder)",
          <label className="inline-flex items-center gap-2 text-sm">
            <input type="checkbox" checked={local.twoFactorEnabled} onChange={(e) => update("twoFactorEnabled", e.target.checked)} />
            {local.twoFactorEnabled ? "Enabled" : "Disabled"}
          </label>
        )}
      </section>

      <div className="flex items-center gap-3">
        <button onClick={save} className="px-4 py-2 rounded bg-orange-500 hover:bg-orange-400 text-black font-semibold text-sm">
          Save Settings
        </button>
        {savedAt && <span className="text-xs text-zinc-400">Saved at {savedAt}</span>}
      </div>
    </div>
  );
}
