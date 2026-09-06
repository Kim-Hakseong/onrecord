/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // `next dev` and `next build` share `.next` by default, so a verification
  // build run while the dev server is up overwrites the chunks the dev server
  // is serving and it starts throwing `Cannot find module './833.js'`.
  // `npm run build` sets NEXT_DIST_DIR so the two never collide.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
