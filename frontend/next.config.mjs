const apiUrl = (process.env.PUREVOICE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export default {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
  },
};
