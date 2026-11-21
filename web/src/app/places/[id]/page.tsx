// 장소 상세 (/places/[id]): 기본 정보 + 분위기 태그 + 블로그 후기 링크
import { Suspense } from "react";
import Link from "next/link";
import { getPlace, WEEKDAYS } from "@/lib/course";

async function PlaceView({ params }: { params: PageProps<"/places/[id]">["params"] }) {
  const { id } = await params;
  const result = await getPlace(id);
  if ("error" in result) return <p className="rounded-lg bg-zinc-100 p-4 dark:bg-zinc-900">{result.error}</p>;
  const p = result.data;
  const mapUrl = `https://map.naver.com/p/search/${encodeURIComponent(`${p.name} ${p.address}`)}`;

  return (
    <>
      <div className="text-sm text-zinc-500">{p.category}{p.naver_category && ` · ${p.naver_category}`}</div>
      <h1 className="mt-1 text-2xl font-bold">{p.name}</h1>
      <dl className="mt-6 grid gap-2 text-sm">
        <div><dt className="inline text-zinc-500">주소 </dt>
          <dd className="inline"><a href={mapUrl} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">{p.address}</a></dd></div>
        {p.phone && <div><dt className="inline text-zinc-500">전화 </dt><dd className="inline"><a href={`tel:${p.phone}`}>{p.phone}</a></dd></div>}
        <div><dt className="inline text-zinc-500">후기 </dt><dd className="inline">{p.review_count}건</dd></div>
      </dl>
      {p.hours && (
        <table className="mt-6 text-sm">
          <caption className="mb-2 text-left font-semibold">영업시간</caption>
          <tbody>
            {WEEKDAYS.filter((d) => d in p.hours!).map((d) => {
              const h = p.hours![d];
              return (
                <tr key={d}>
                  <th scope="row" className="pr-4 text-left font-normal text-zinc-500">{d}</th>
                  <td>
                    {h ? `${h.open}~${h.close}` : "휴무"}
                    {h?.breaks.length ? ` · 브레이크 ${h.breaks.map(([s, e]) => `${s}~${e}`).join(", ")}` : ""}
                    {h?.last_order ? ` · 라스트오더 ${h.last_order}` : ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {p.moods && p.moods.length > 0 && (
        <ul className="mt-4 flex flex-wrap gap-2">
          {p.moods.map((m) => <li key={m} className="rounded-full border border-zinc-300 px-3 py-1 text-sm dark:border-zinc-700">{m}</li>)}
        </ul>
      )}
      <h2 className="mt-10 font-semibold">블로그 후기</h2>
      <ul className="mt-3 grid gap-3">
        {p.reviews.map((r) => (
          <li key={r.url}>
            <a href={r.url} target="_blank" rel="noopener noreferrer" className="underline-offset-4 hover:underline">{r.title || r.url}</a>
            <div className="text-xs text-zinc-500">
              {r.platform}{r.posted_at && ` · ${r.posted_at}`}{r.is_negative && " · 아쉬운 후기"}
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

export default function PlacePage(props: PageProps<"/places/[id]">) {
  return (
    <main className="mx-auto w-full max-w-xl px-4 py-12">
      <Link href="/" className="text-sm text-zinc-500">← 처음으로</Link>
      <div className="mt-4">
        <Suspense fallback={<p className="text-zinc-500">불러오는 중…</p>}>
          <PlaceView params={props.params} />
        </Suspense>
      </div>
    </main>
  );
}
