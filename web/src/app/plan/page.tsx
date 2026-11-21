// 세부 입력 화면 (/plan?mode=...): 선택한 경우별 입력 폼. 제출하면 /course?... 로 이동
// URL 파라미터를 읽는 부분은 Cache Components 규칙상 <Suspense> 안에 있어야 함
import { Suspense } from "react";
import Form from "next/form";
import Link from "next/link";
import { redirect } from "next/navigation";
import { MODES, MOODS, TRANSPORTS } from "@/lib/course";

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
            <Field label="지역" name="region" required placeholder="예: 강원도 강릉" />
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
        <Field label="출발 시간" name="start" type="time" defaultValue="09:00" required />
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
