// PWA 설정: 휴대폰 브라우저에서 "홈 화면에 추가"하면 앱처럼 전체화면으로 실행 (HTTPS 배포 필요, localhost는 예외)
import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "어디갈까",
    short_name: "어디갈까",
    description: "지역·교통수단·분위기로 여행 코스를 추천합니다",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#18181b",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
