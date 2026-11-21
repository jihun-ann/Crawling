// 세부 입력 화면 (/plan?mode=...): 선택한 경우별 입력 폼. 제출하면 /course?... 로 이동
// URL 파라미터를 읽는 부분은 Cache Components 규칙상 <Suspense> 안에 있어야 함
import { Suspense } from "react";
import Form from "next/form";
import Link from "next/link";
import { redirect } from "next/navigation";
import { MODES, MOODS, TRANSPORTS, getSpotTypes } from "@/lib/course";

const input = "w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700";

function Field({ label, ...props }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="grid gap-1 text-sm font-medium">
      {label}
      <input className={input} {...props} />
    </label>
  );
}

function Choice({ label, name, options }: { label: string; name: string; options: string[] }) {
  return (
    <fieldset className="grid gap-2 text-sm font-medium">
      <legend className="mb-1">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((o, i) => (
          <label key={o} className="cursor-pointer rounded-full border border-zinc-300 px-4 py-2 has-checked:border-zinc-900 has-checked:bg-zinc-900 has-checked:text-white dark:border-zinc-700 dark:has-checked:bg-zinc-100 dark:has-checked:text-zinc-900">
            <input type="radio" name={name} value={o} defaultChecked={i === 0} className="sr-only" />
            {o}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

// 가볼만한 곳 종류 선택. 선택지는 크롤링으로 수집된 장소의 업종에서 나옴 (고정 목록 없음)
// 어느 곳으로 갈지는 시스템이 숙소·지역 기준으로 고름
async function SpotTypeSelect() {
  const result = await getSpotTypes();
  const types = "data" in result ? result.data : [];
  return (
    <label className="grid gap-1 text-sm font-medium">
      가볼만한 곳 (선택)
      <select name="spot_type" defaultValue="" className={input}>
        <option value="">선택 안 함</option>
        {types.map((t) => <option key={t.type} value={t.type}>{t.type}</option>)}
      </select>
      {types.length === 0 && <span className="text-xs font-normal text-zinc-500">아직 수집된 장소가 없어요.</span>}
    </label>
  );
}

async function PlanForm({ searchParams }: { searchParams: PageProps<"/plan">["searchParams"] }) {
  const { mode } = await searchParams;
  const m = MODES.find((x) => x.id === mode && x.id !== "random");
  if (!m) redirect("/");

  return (
    <>
      <h1 className="text-2xl font-bold">{m.label}</h1>
      <Form action="/course" className="mt-8 grid gap-5">
        <input type="hidden" name="mode" value={m.id} />
        {m.id === "region" && (
          <>
            <Field label="지역" name="region" placeholder="예: 강원도 강릉 (가볼만한 곳만 골랐다면 비워도 돼요)" />
            <SpotTypeSelect />
            <Field label="숙소 (선택)" name="stay" placeholder="숙소 이름 또는 주소" />
          </>
        )}
        {m.id === "transport" && (
          <>
            <Choice label="교통수단" name="transport" options={TRANSPORTS} />
            <Field label="출발지" name="from" required placeholder="예: 서울역" />
          </>
        )}
        {m.id === "mood" && (
          <>
            <Choice label="분위기" name="mood" options={MOODS} />
            <Field label="출발지" name="from" required placeholder="예: 서울역" />
          </>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="날짜 (비우면 오늘)" name="date" type="date" />
          <Field label="출발 시간" name="start" type="time" defaultValue="09:00" required />
        </div>
        <button className="mt-2 rounded-lg bg-zinc-900 py-3 font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
          코스 추천받기
        </button>
      </Form>
    </>
  );
}

export default function PlanPage(props: PageProps<"/plan">) {
  return (
    <main className="mx-auto w-full max-w-xl px-4 py-12">
      <Link href="/" className="text-sm text-zinc-500">← 처음으로</Link>
      <div className="mt-4">
        <Suspense fallback={null}>
          <PlanForm searchParams={props.searchParams} />
        </Suspense>
      </div>
    </main>
  );
}
