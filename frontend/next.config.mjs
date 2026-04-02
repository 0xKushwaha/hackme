/** @type {import('next').NextConfig} */
const nextConfig = {
  // Needed for Three.js / react-three-fiber
  transpilePackages: ['three'],
  // StrictMode double-mounts components, exhausting the browser's WebGL context limit
  reactStrictMode: false,
}

export default nextConfig
