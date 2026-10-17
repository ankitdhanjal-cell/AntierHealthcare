import "./globals.css";
import type { Metadata } from "next";
import { Providers } from "@/components/Providers";

export const metadata: Metadata = {
  title: { default: "Antier Healthcare Suite", template: "%s · Antier Healthcare Suite" },
  description: "Patient experience and quality management for hospitals.",
  icons: { icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='8' fill='%230f766e'/><path d='M14 7h4v7h7v4h-7v7h-4v-7H7v-4h7z' fill='white'/></svg>" },
};

export default function Root({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en"><body><Providers>{children}</Providers></body></html>
  );
}
