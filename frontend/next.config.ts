import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "op.onbid.co.kr",
      },
    ],
  },
  async rewrites() {
    // 컨테이너 배포 시 compose 가 API_INTERNAL=http://onbid_api:8000 주입.
    // 로컬 개발에선 기본값(localhost:8000) 유지.
    const api = process.env.API_INTERNAL ?? "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${api}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
