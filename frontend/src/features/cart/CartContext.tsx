/**
 * Cart state shared by the storefront.
 *
 * The backend is the single source of truth: the cart is loaded once on app
 * start (so it survives a page refresh and follows the visitor between pages)
 * and every mutation replaces local state with the authoritative cart the API
 * returns. Prices, totals and stock figures are never computed in the client.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  addCartItem,
  clearCart,
  getCart,
  removeCartItem,
  updateCartItem,
} from "../../api/cart";
import { ApiError } from "../../api/http";
import type { Cart, CartItem } from "../../types/cart";

export type CartMutationResult = { ok: true } | { ok: false; error: string };

interface CartContextValue {
  cart: Cart | null;
  items: CartItem[];
  totalQuantity: number;
  subtotal: string;
  hasStockConflicts: boolean;
  isLoading: boolean;
  isMutating: boolean;
  error: string | null;
  addItem: (variantId: string, quantity?: number) => Promise<CartMutationResult>;
  updateQuantity: (itemId: number, quantity: number) => Promise<CartMutationResult>;
  removeItem: (itemId: number) => Promise<CartMutationResult>;
  clear: () => Promise<CartMutationResult>;
  refresh: () => Promise<void>;
  dismissError: () => void;
}

const CartContext = createContext<CartContextValue | null>(null);

function toMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something went wrong. Please try again.";
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    try {
      const next = await getCart();
      if (!mountedRef.current) return;
      setCart(next);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(toMessage(err));
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, []);

  // Load the persisted cart (guest session or customer) on app start.
  useEffect(() => {
    void refresh();
  }, [refresh]);

  const runMutation = useCallback(
    async (mutation: () => Promise<Cart>): Promise<CartMutationResult> => {
      setIsMutating(true);
      try {
        const next = await mutation();
        if (mountedRef.current) {
          setCart(next);
          setError(null);
        }
        return { ok: true };
      } catch (err) {
        const message = toMessage(err);
        if (mountedRef.current) setError(message);
        return { ok: false, error: message };
      } finally {
        if (mountedRef.current) setIsMutating(false);
      }
    },
    [],
  );

  const addItem = useCallback(
    (variantId: string, quantity = 1) =>
      runMutation(() => addCartItem(variantId, quantity)),
    [runMutation],
  );

  const updateQuantity = useCallback(
    (itemId: number, quantity: number) =>
      runMutation(() => updateCartItem(itemId, quantity)),
    [runMutation],
  );

  const removeItem = useCallback(
    (itemId: number) => runMutation(() => removeCartItem(itemId)),
    [runMutation],
  );

  const clear = useCallback(() => runMutation(() => clearCart()), [runMutation]);

  const dismissError = useCallback(() => setError(null), []);

  const value = useMemo<CartContextValue>(
    () => ({
      cart,
      items: cart?.items ?? [],
      totalQuantity: cart?.total_quantity ?? 0,
      subtotal: cart?.subtotal ?? "0.00",
      hasStockConflicts: cart?.has_stock_conflicts ?? false,
      isLoading,
      isMutating,
      error,
      addItem,
      updateQuantity,
      removeItem,
      clear,
      refresh,
      dismissError,
    }),
    [
      cart,
      isLoading,
      isMutating,
      error,
      addItem,
      updateQuantity,
      removeItem,
      clear,
      refresh,
      dismissError,
    ],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const context = useContext(CartContext);
  if (context === null) {
    throw new Error("useCart must be used inside a CartProvider");
  }
  return context;
}
