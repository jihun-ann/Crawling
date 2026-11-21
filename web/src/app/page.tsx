// 진입 화면 (/): 지역 / 교통수단 / 분위기 / 랜덤 중 선택. 랜덤은 입력 없이 바로 결과로 이동
import Link from "next/link";
import { MODES } from "@/lib/course";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-xl px-4 py-12">
      <h1 className="text-2xl font-bold">어디로 갈까요?</h1>
      <p className="mt-2 text-zinc-600 dark:text-zinc-400">정해진 것부터 골라주세요.</p>
      <ul className="mt-8 grid gap-3">
        {MODES.map((m) => (
          <li key={m.id}>
            <Link
              href={m.id === "random" ? "/course?mode=random" : `/plan?mode=${m.id}`}
              className="block rounded-xl border border-zinc-200 p-5 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
            >
              <div className="font-semibold">{m.label}</div>
              <div className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{m.desc}</div>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
