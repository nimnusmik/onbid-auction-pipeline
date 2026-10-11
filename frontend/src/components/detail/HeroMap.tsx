// frontend/src/components/detail/HeroMap.tsx
"use client";

import { useEffect, useRef } from "react";

declare global {
  interface Window {
    kakao: any; // eslint-disable-line @typescript-eslint/no-explicit-any
  }
}

const KAKAO_KEY = process.env.NEXT_PUBLIC_KAKAO_MAP_KEY ?? "";

interface Props {
  address: string;       // "서울특별시 강남구 역삼동"
  labelSggn: string;     // "강남구" (마커 라벨)
  className?: string;    // 외부에서 크기/모양 주입
}

export default function HeroMap({ address, labelSggn, className }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInitialized = useRef(false);

  useEffect(() => {
    if (!KAKAO_KEY || !mapRef.current || mapInitialized.current) return;

    function initMap() {
      if (!mapRef.current || mapInitialized.current) return;
      mapInitialized.current = true;

      window.kakao.maps.load(() => {
        const geocoder = new window.kakao.maps.services.Geocoder();
        geocoder.addressSearch(address, (result: any[], status: string) => {
          if (!mapRef.current) return;
          const coords =
            status === window.kakao.maps.services.Status.OK
              ? new window.kakao.maps.LatLng(parseFloat(result[0].y), parseFloat(result[0].x))
              : new window.kakao.maps.LatLng(37.5665, 126.978);

          const map = new window.kakao.maps.Map(mapRef.current, {
            center: coords,
            level: 4,
          });
          new window.kakao.maps.Marker({ position: coords, map });
          new window.kakao.maps.CustomOverlay({
            position: coords,
            map,
            content: `<div style="
              background:var(--color-primary);color:#fff;font-size:11px;font-weight:700;
              padding:4px 10px;border-radius:99px;white-space:nowrap;
              box-shadow:0 1px 4px rgba(0,0,0,.25);margin-bottom:42px;
            ">${labelSggn}</div>`,
            yAnchor: 1,
          });
        });
      });
    }

    if (window.kakao?.maps?.load) {
      initMap();
      return;
    }

    const script = document.createElement("script");
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_KEY}&libraries=services&autoload=false`;
    script.onload = initMap;
    document.head.appendChild(script);
  }, [address, labelSggn]);

  if (!KAKAO_KEY) {
    return (
      <div className={`bg-surface-muted rounded-lg flex flex-col items-center justify-center gap-2 p-4 text-center ${className ?? ""}`}>
        <div className="w-10 h-10 bg-[#FEE500] rounded-full flex items-center justify-center text-lg">🗺️</div>
        <p className="text-xs font-medium text-text-2">카카오맵 API 키 필요</p>
        <p className="text-[10px] text-text-4 leading-relaxed">
          <code className="bg-border px-1 rounded">NEXT_PUBLIC_KAKAO_MAP_KEY</code>
        </p>
        <p className="text-[11px] text-primary font-medium">{address}</p>
      </div>
    );
  }

  return <div ref={mapRef} className={className ?? "w-full h-full"} />;
}
