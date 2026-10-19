"use client";
import { NotFoundPanel } from "@/components/NotFound";
import { Shell } from "@/components/Shell";

// Unknown URLs: show the branded page inside the app shell (the shell sends signed-out visitors to /login).
export default function NotFound() {
  return <Shell><NotFoundPanel /></Shell>;
}
