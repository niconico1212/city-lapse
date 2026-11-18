import type { NextConfig } from "next";

// Fully static site: `next build` writes plain files to out/, which is what Vercel serves.
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  reactStrictMode: true,
};

export default nextConfig;
