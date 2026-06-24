import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    mcpServer: false,
  },
};

export default nextConfig;
