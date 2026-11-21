"use client";
// 코스 지도 (네이버 지도 JS API). NEXT_PUBLIC_NAVER_MAP_CLIENT_ID 없으면 아무것도 그리지 않음
// 키 발급: 네이버 클라우드 플랫폼 > Maps > Application 등록 (Web 서비스 URL에 http://localhost:3000 추가)
import Script from "next/script";
import { useRef } from "react";

type Point = { lat: number; lng: number; label: string };

/* eslint-disable @typescript-eslint/no-explicit-any -- 네이버 지도 SDK는 타입 정의가 없음 */
declare global {
  interface Window { naver?: any }
}

export default function CourseMap({ points }: { points: Point[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const key = process.env.NEXT_PUBLIC_NAVER_MAP_CLIENT_ID;
  if (!key || points.length === 0) return null;

  const draw = () => {
    const n = window.naver?.maps;
    if (!n || !ref.current) return;
    const path = points.map((p) => new n.LatLng(p.lat, p.lng));
    const map = new n.Map(ref.current, { center: path[0], zoom: 15 });
    if (path.length > 1) {
      const bounds = new n.LatLngBounds(path[0], path[0]);
      path.forEach((p: any) => bounds.extend(p));
      map.fitBounds(bounds, { top: 40, right: 40, bottom: 40, left: 40 });
    }
    path.forEach((position: any, i: number) => new n.Marker({
      position, map, title: points[i].label,
      icon: { content: `<div style="background:#18181b;color:#fff;border-radius:9999px;width:26px;height:26px;display:grid;place-items:center;font:600 13px sans-serif">${i}</div>` },
    }));
    new n.Polyline({ map, path, strokeColor: "#18181b", strokeWeight: 3, strokeOpacity: 0.7 });
  };

  return (
    <>
      <Script src={`https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${key}`} onReady={draw} />
      <div ref={ref} className="mt-6 h-72 w-full overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800" />
    </>
  );
}
