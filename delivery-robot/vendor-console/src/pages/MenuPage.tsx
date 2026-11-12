import { useMemo, useState } from "react";
import { useMenu } from "../hooks/useMenu";
import type { MenuItem } from "../types";

interface MenuPageProps {
  isLight?: boolean;
  vendorId: number | null;
}

type FormData = Omit<MenuItem, "id">;

const EMPTY_FORM: FormData = {
  name: "",
  category: "",
  price: 0,
  description: "",
  imageUrl: "",
  prepTimeMins: 5,
  isAvailable: true,
};

export default function MenuPage({ isLight = false, vendorId }: MenuPageProps) {
  const { items, isLoading, error, clearError, addItem, saveItem, removeItem, toggleAvailable } =
    useMenu(vendorId);

  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const kioskPayload = useMemo(
    () =>
      JSON.stringify(
        items
          .filter((item) => item.isAvailable)
          .map(({ id, name, category, price, description, imageUrl, prepTimeMins }) => ({
            id,
            name,
            category,
            price,
            description,
            imageUrl,
            prepTimeMins,
          })),
        null,
        2,
      ),
    [items],
  );

  function openAdd() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  }

  function openEdit(item: MenuItem) {
    setEditingId(item.id);
    setForm({
      name: item.name,
      category: item.category,
      price: item.price,
      description: item.description,
      imageUrl: item.imageUrl,
      prepTimeMins: item.prepTimeMins,
      isAvailable: item.isAvailable,
    });
    setShowForm(true);
  }

  function closeForm() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setShowForm(false);
  }

  async function handleSubmit() {
    if (!form.name.trim()) return;
    setSaving(true);
    clearError();
    if (editingId) {
      await saveItem(editingId, form);
    } else {
      await addItem(form);
    }
    setSaving(false);
    closeForm();
  }

  const inputClass = `px-3 py-2 rounded border text-sm ${isLight ? "bg-white border-zinc-300 text-zinc-900" : "bg-zinc-800 border-zinc-700 text-zinc-100"}`;

  return (
    <div className="p-5 h-full overflow-y-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-mono text-lg font-semibold">Menu Management</h2>
        <button
          onClick={showForm ? closeForm : openAdd}
          className="px-4 py-2 rounded bg-orange-500 hover:bg-orange-400 text-black font-semibold text-sm"
        >
          {showForm ? "Hide Form" : "Add New Item"}
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center justify-between gap-3 px-4 py-3 rounded border border-red-500/30 bg-red-500/10 text-red-400 text-sm">
          <span>{error}</span>
          <button onClick={clearError} className="text-xs underline shrink-0">
            Dismiss
          </button>
        </div>
      )}

      {/* Add / Edit form */}
      {showForm && (
        <div
          className={`rounded p-4 grid md:grid-cols-2 gap-3 border ${isLight ? "bg-white border-zinc-300" : "bg-zinc-900 border-zinc-800"}`}
        >
          <input
            className={inputClass}
            placeholder="Item name *"
            value={form.name}
            onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
          />
          <input
            className={inputClass}
            placeholder="Category"
            value={form.category}
            onChange={(e) => setForm((p) => ({ ...p, category: e.target.value }))}
          />
          <label className="block">
            <span className="text-xs text-zinc-400 mb-1 block">Price ($)</span>
            <input
              type="number"
              className={inputClass + " w-full"}
              placeholder="e.g. 8.99"
              value={form.price}
              onChange={(e) => setForm((p) => ({ ...p, price: Number(e.target.value) }))}
            />
          </label>
          <label className="block">
            <span className="text-xs text-zinc-400 mb-1 block">Prep time (mins)</span>
            <input
              type="number"
              className={inputClass + " w-full"}
              placeholder="e.g. 10"
              value={form.prepTimeMins}
              onChange={(e) => setForm((p) => ({ ...p, prepTimeMins: Number(e.target.value) }))}
            />
          </label>
          <input
            className={`${inputClass} md:col-span-2`}
            placeholder="Description"
            value={form.description}
            onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
          />
          <input
            className={`${inputClass} md:col-span-2`}
            placeholder="Image URL (for kiosk)"
            value={form.imageUrl}
            onChange={(e) => setForm((p) => ({ ...p, imageUrl: e.target.value }))}
          />
          <div className="md:col-span-2 flex gap-2">
            <button
              onClick={handleSubmit}
              disabled={saving || !form.name.trim()}
              className="px-4 py-2 rounded bg-orange-500 hover:bg-orange-400 disabled:opacity-50 disabled:cursor-not-allowed text-black font-semibold text-sm"
            >
              {saving ? "Saving…" : editingId ? "Save Item" : "Add Menu Item"}
            </button>
            <button
              onClick={closeForm}
              className={`px-4 py-2 rounded border text-sm ${isLight ? "border-zinc-300 hover:bg-zinc-100" : "border-zinc-700 hover:bg-zinc-800"}`}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div
        className={`rounded overflow-hidden border ${isLight ? "bg-white border-zinc-300" : "bg-zinc-900 border-zinc-800"}`}
      >
        {isLoading ? (
          <div className="flex items-center justify-center gap-3 py-12 font-mono text-sm text-zinc-400">
            <span className="w-4 h-4 rounded-full border-2 border-orange-500 border-t-transparent animate-spin" />
            Loading menu…
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className={isLight ? "bg-zinc-100 text-zinc-600" : "bg-zinc-800 text-zinc-400"}>
              <tr>
                <th className="text-left px-3 py-2">Name</th>
                <th className="text-left px-3 py-2">Category</th>
                <th className="text-left px-3 py-2">Image</th>
                <th className="text-left px-3 py-2">Price</th>
                <th className="text-left px-3 py-2">Available</th>
                <th className="text-left px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-3 py-10 text-center font-mono text-xs text-zinc-500"
                  >
                    No menu items yet. Add your first item above.
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr
                    key={item.id}
                    className={`border-t ${isLight ? "border-zinc-200" : "border-zinc-800"}`}
                  >
                    <td className="px-3 py-2 font-medium">{item.name}</td>
                    <td className={`px-3 py-2 text-xs ${isLight ? "text-zinc-500" : "text-zinc-400"}`}>
                      {item.category || "—"}
                    </td>
                    <td className="px-3 py-2">
                      {item.imageUrl ? (
                        <img
                          src={item.imageUrl}
                          alt={item.name}
                          className="w-10 h-10 object-cover rounded border border-zinc-300"
                        />
                      ) : (
                        <span className="text-xs text-zinc-500">No image</span>
                      )}
                    </td>
                    <td className="px-3 py-2">${item.price.toFixed(2)}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`font-mono text-xs ${item.isAvailable ? "text-green-400" : "text-zinc-500"}`}
                      >
                        {item.isAvailable ? "Yes" : "No"}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex gap-2">
                        <button
                          onClick={() => openEdit(item)}
                          className="px-2 py-1 rounded border border-blue-500/40 text-blue-300 text-xs hover:bg-blue-500/10"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => toggleAvailable(item.id)}
                          className={`px-2 py-1 rounded border text-xs ${isLight ? "border-zinc-300 hover:bg-zinc-100" : "border-zinc-600 hover:bg-zinc-800"}`}
                        >
                          Toggle
                        </button>
                        <button
                          onClick={() => removeItem(item.id)}
                          className="px-2 py-1 rounded border border-red-500/40 text-red-300 text-xs hover:bg-red-500/10"
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Kiosk payload preview */}
      <div>
        <h3 className={`font-mono text-sm mb-2 ${isLight ? "text-zinc-600" : "text-zinc-300"}`}>
          Kiosk payload preview
        </h3>
        <pre
          className={`border rounded p-3 text-xs overflow-x-auto ${isLight ? "bg-white border-zinc-300" : "bg-zinc-900 border-zinc-800"}`}
        >
          {kioskPayload}
        </pre>
      </div>
    </div>
  );
}
