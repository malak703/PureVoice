import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PureVoice | Vocal & Daf Studio",
  description: "Separate vocals and generate Daf percussion that follows your song.",
};

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
