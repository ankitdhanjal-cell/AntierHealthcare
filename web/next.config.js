/** @type {import('next').NextConfig} */
module.exports = {
  ...(process.env.STANDALONE ? { output: "standalone" } : {}),
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.API_INTERNAL_URL || "http://localhost:8010"}/api/:path*` }];
  },
};
