// 결과 화면 (/course?...): URL 파라미터로 FastAPI 코스 추천 API 호출 → 지도 + 시간순 타임라인 + 단계별 대체 후보
import { Suspense } from "react";
import Link from "next/link";
import { getCourse, type Place } from "@/lib/course";
import CourseMap from "./course-map";

const naverMapUrl = (p: Place) => `https://map.naver.com/p/search/${encodeURIComponent(`${p.name} ${p.address}`)}`;

function PlaceName({ place }: { place: Place }) {
  return place.id > 0
    ? <Link href={`/places/${place.id}`} className="underline-offset-4 hover:underline">{place.name}</Link>
    : <>{place.name}</>;
}

async function CourseView({ searchParams }: { searchParams: PageProps<"/course">["searchParams"] }) {
  const raw = await searchParams;
  const params = Object.fromEntries(Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]));
  const result = await getCourse(params);
  if ("error" in result) return <p className="rounded-lg bg-zinc-100 p-4 dark:bg-zinc-900">{result.error}</p>;
  const course = result.data;

  return (
    <>
      <h1 className="text-2xl font-bold">{course.title}</h1>
      {course.date && <p className="mt-1 text-sm text-zinc-500">{course.date} ({course.weekday}) 영업시간 기준</p>}
      {course.message && <p className="mt-4 rounded-lg bg-zinc-100 p-4 dark:bg-zinc-900">{course.message}</p>}
      <CourseMap points={course.steps.map((s) => ({ lat: s.place.lat, lng: s.place.lng, label: s.place.name }))} />
      <ol className="mt-8 border-l-2 border-zinc-200 dark:border-zinc-800">
        {course.steps.map((s, i) => (
          <li key={`${i}-${s.place.id}`} className="relative mb-8 pl-6">
            <span className="absolute -left-[7px] top-1.5 h-3 w-3 rounded-full bg-zinc-900 dark:bg-zinc-100" />
            <div className="text-sm text-zinc-500">
              {s.time} · {s.category}{s.travel_min > 0 && ` · 이동 약 ${s.travel_min}분`}
            </div>
            <div className="mt-1 text-lg font-semibold"><PlaceName place={s.place} /></div>
            {s.hours_today && <div className="text-sm text-zinc-600 dark:text-zinc-400">영업 {s.hours_today}</div>}
            {s.warning && <div className="mt-1 text-sm font-medium text-amber-700 dark:text-amber-400">⚠ {s.warning}</div>}
            {s.place.address && (
              <a href={naverMapUrl(s.place)} target="_blank" rel="noopener noreferrer"
                 className="text-sm text-zinc-600 underline-offset-4 hover:underline dark:text-zinc-400">
                {s.place.address}
              </a>
            )}
            {s.alternatives.length > 0 && (
              <details className="mt-2 text-sm">
                <summary className="cursor-pointer text-zinc-500">다른 {s.category} {s.alternatives.length}곳</summary>
                <ul className="mt-2 grid gap-1">
                  {s.alternatives.map((a) => <li key={a.id}><PlaceName place={a} /></li>)}
                </ul>
              </details>
            )}
          </li>
        ))}
      </ol>
    </>
  );
}

export default function CoursePage(props: PageProps<"/course">) {
  return (
    <main className="mx-auto w-full max-w-xl px-4 py-12">
      <Link href="/" className="text-sm text-zinc-500">← 처음으로</Link>
      <div className="mt-4">
        <Suspense fallback={<p className="text-zinc-500">코스를 만드는 중…</p>}>
          <CourseView searchParams={props.searchParams} />
        </Suspense>
      </div>
    </main>
  );
}
