/** @type {import('next').NextConfig} */
const backend = (process.env.BACKEND_URL || "").replace(/\/$/, "");

const nextConfig = {
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },
  // Запасной путь против CORS: если NEXT_PUBLIC_API_URL не задан, фронтенд ходит на /backend/*,
  // а Vercel проксирует запрос на BACKEND_URL (адрес Hugging Face Space).
  async rewrites() {
    return backend ? [{ source: "/backend/:path*", destination: `${backend}/:path*` }] : [];
  },
};

module.exports = nextConfig;
