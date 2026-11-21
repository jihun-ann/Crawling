// 화면 공용 상수(경우/교통수단/분위기), API 응답 타입, 백엔드 호출 함수
export type Mode = "region" | "transport" | "mood" | "random";

export const MODES: { id: Mode; label: string; desc: string }[] = [
  { id: "region", label: "지역이 정해졌어요", desc: "갈 지역이나 숙소가 정해진 경우" },
  { id: "transport", label: "교통수단만 정했어요", desc: "무엇을 타고 갈지만 정한 경우" },
  { id: "mood", label: "분위기로 고를래요", desc: "조용한 곳, 할 게 많은 곳 등" },
  { id: "random", label: "랜덤으로 추천받기", desc: "아무것도 안 정했어요" },
];

export const TRANSPORTS = ["자동차", "대중교통", "KTX/기차", "도보"];
export const MOODS = ["조용한", "할 게 많은", "자연", "감성/사진"];

// 요일별 영업시간 (API hours.py 저장 형식). null = 휴무, 키 없음 = 정보 없음
export type DayHours = { open: string; close: string; breaks: [string, string][]; last_order: string | null } | null;
export type Place = {
  id: number; name: string; category: string; address: string;
  lat: number; lng: number; score?: number; moods?: string[]; review_count?: number; phone?: string | null;
  city?: string | null; hours?: Record<string, DayHours> | null;
};
export type Step = {
  time: string; category: string; travel_min: number; place: Place; alternatives: Place[];
  hours_today: string | null; warning: string | null;
};
export type Course = { title: string; message: string | null; date?: string; weekday?: string; steps: Step[] };
export const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];
export type Review = { title: string; url: string; platform: string; posted_at: string | null; is_negative: boolean };
export type PlaceDetail = Place & { naver_category: string | null; reviews: Review[] };

const API_URL = process.env.API_URL ?? "http://localhost:8000";

// 서버 컴포넌트에서 호출 → 서버 간 통신이라 CORS 불필요
// 4xx(위치 못 찾음 등)는 API의 안내 문구를 그대로 반환해 화면에 표시. 서버 다운 등은 throw → app/error.tsx
async function api<T>(path: string): Promise<{ data: T } | { error: string }> {
  const res = await fetch(`${API_URL}${path}`);
  if (res.ok) return { data: await res.json() };
  if (res.status >= 500) throw new Error(`API 오류 ${res.status}`);
  const body = await res.json().catch(() => ({}));
  return { error: typeof body.detail === "string" ? body.detail : "요청을 처리할 수 없어요." };
}

export function getCourse(params: Record<string, string | undefined>) {
  const query = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => !!e[1]));
  return api<Course>(`/courses/recommend?${query}`);
}

// 크롤링으로 저장된 테마파크 목록 (지역 선택 화면의 선택지)
export function getThemeParks() {
  return api<Place[]>(`/places?category=${encodeURIComponent("테마파크")}&limit=200`);
}

export function getPlace(id: string) {
  return api<PlaceDetail>(`/places/${encodeURIComponent(id)}`);
}
