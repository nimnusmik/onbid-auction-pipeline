// frontend/src/hooks/useMarketPrice.ts
"use client";

import { useEffect, useRef, useState } from "react";
import { fetchMarketPrice } from "@/api";
import type { MarketPriceResponse } from "@/types";

const cache = new Map<string, MarketPriceResponse>();

interface State {
  market: MarketPriceResponse | null;
  loading: boolean;
  error: string | null;
}

export function useMarketPrice(id: string | null | undefined): State {
  const [state, setState] = useState<State>(() => ({
    market: id && cache.has(id) ? cache.get(id)! : null,
    loading: !!id && !cache.has(id),
    error: null,
  }));
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    if (!id) {
      setState({ market: null, loading: false, error: null });
      return;
    }
    if (cache.has(id)) {
      setState({ market: cache.get(id)!, loading: false, error: null });
      return;
    }
    setState({ market: null, loading: true, error: null });
    fetchMarketPrice(id)
      .then((res) => {
        cache.set(id, res);
        if (alive.current) setState({ market: res, loading: false, error: null });
      })
      .catch((e: Error) => {
        if (alive.current) setState({ market: null, loading: false, error: e.message });
      });
  }, [id]);

  return state;
}
