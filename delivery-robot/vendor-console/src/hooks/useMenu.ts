import { useCallback, useEffect, useRef, useState } from "react";
import {
  type MenuItemFormData,
  createMenuItem,
  deleteMenuItem,
  fetchMenuItems,
  updateMenuItem,
} from "../api/menu";
import type { MenuItem } from "../types";

export function useMenu(vendorId: number | null) {
  const [items, setItems] = useState<MenuItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const vendorIdRef = useRef<number | null>(null);
  vendorIdRef.current = vendorId;

  useEffect(() => {
    let cancelled = false;
    setError(null);

    if (vendorId == null) {
      setItems([]);
      setIsLoading(true);
      return;
    }

    setIsLoading(true);

    fetchMenuItems(vendorId)
      .then((loadedItems) => {
        if (cancelled) return;
        setItems(loadedItems);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("Failed to load menu:", err);
        setError("Could not load menu items. Check that the backend is running.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [vendorId]);

  const addItem = useCallback(
    async (form: Omit<MenuItemFormData, "vendorId">): Promise<boolean> => {
      const vendorId = vendorIdRef.current;
      if (!vendorId) {
        setError("No vendor account found. Please contact your administrator.");
        return false;
      }
      try {
        const created = await createMenuItem({ ...form, vendorId });
        setItems((prev) => [created, ...prev]);
        return true;
      } catch (err) {
        console.error("Failed to create menu item:", err);
        setError("Could not create item. Please try again.");
        return false;
      }
    },
    [],
  );

  const saveItem = useCallback(
    async (id: string, form: Partial<MenuItemFormData>): Promise<boolean> => {
      const vid = vendorIdRef.current;
      if (vid == null) return false;
      // Optimistic update
      setItems((prev) =>
        prev.map((item) =>
          item.id === id
            ? {
                ...item,
                ...(form.name !== undefined && { name: form.name }),
                ...(form.description !== undefined && { description: form.description }),
                ...(form.price !== undefined && { price: form.price }),
                ...(form.isAvailable !== undefined && { isAvailable: form.isAvailable }),
                ...(form.prepTimeMins !== undefined && { prepTimeMins: form.prepTimeMins }),
                ...(form.category !== undefined && { category: form.category }),
                ...(form.imageUrl !== undefined && { imageUrl: form.imageUrl }),
              }
            : item,
        ),
      );
      try {
        const updated = await updateMenuItem(vid, id, form);
        setItems((prev) => prev.map((item) => (item.id === id ? updated : item)));
        return true;
      } catch (err) {
        console.error("Failed to update menu item:", err);
        // Revert by re-fetching
        fetchMenuItems(vid)
          .then(setItems)
          .catch(() => null);
        setError("Could not save changes. Please try again.");
        return false;
      }
    },
    [],
  );

  const removeItem = useCallback(async (id: string): Promise<void> => {
    const vid = vendorIdRef.current;
    if (vid == null) return;
    setItems((prev) => prev.filter((item) => item.id !== id));
    try {
      await deleteMenuItem(vid, id);
    } catch (err) {
      console.error("Failed to delete menu item:", err);
      // Revert
      fetchMenuItems(vid)
        .then(setItems)
        .catch(() => null);
      setError("Could not delete item. Please try again.");
    }
  }, []);

  const toggleAvailable = useCallback(
    async (id: string): Promise<void> => {
      const current = items.find((i) => i.id === id);
      if (!current) return;
      await saveItem(id, { isAvailable: !current.isAvailable });
    },
    [items, saveItem],
  );

  const clearError = useCallback(() => setError(null), []);

  return {
    items,
    isLoading,
    error,
    clearError,
    addItem,
    saveItem,
    removeItem,
    toggleAvailable,
  };
}
