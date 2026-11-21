"use client";
// 예상 못 한 오류(API 서버 꺼짐 등) 화면. 위치 못 찾음 같은 안내는 각 페이지에서 직접 표시
import Link from "next/link";

export default function Error({ retry }: { error: unknown; retry: () => void }) {
  return (
    <main className="mx-auto w-full max-w-xl px-4 py-12">
      <h1 className="text-xl font-bold">잠시 문제가 생겼어요</h1>
      <p className="mt-2 text-zinc-600 dark:text-zinc-400">추천 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.</p>
      <div className="mt-6 flex gap-3">
        <button onClick={() => retry()} className="rounded-lg bg-zinc-900 px-4 py-2 font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
          다시 시도
        </button>
        <Link href="/" className="rounded-lg border border-zinc-300 px-4 py-2 dark:border-zinc-700">처음으로</Link>
      </div>
    </main>
  );
}
