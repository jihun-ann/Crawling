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

export type Place = { id: number; name: string; category: string; address: string };
export type Step = { time: string; category: string; place: Place; alternatives: Place[] };
export type Course = { title: string; steps: Step[] };

const API_URL = process.env.API_URL ?? "http://localhost:8000";

// 서버 컴포넌트에서 호출 → 서버 간 통신이라 CORS 불필요
export async function getCourse(params: Record<string, string | undefined>): Promise<Course> {
  const query = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => !!e[1]));
  const res = await fetch(`${API_URL}/courses/recommend?${query}`);
  if (!res.ok) throw new Error(`코스 추천 API 오류 ${res.status}`);
  return res.json();
}
