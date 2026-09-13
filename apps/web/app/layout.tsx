import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "CommitmentOS — Autonomous Commitment Recovery",
  description:
    "CommitmentOS turns organizational promises into observable, actionable, verifiable work.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <div style={{ display: "flex", minHeight: "100vh" }}>
          <Sidebar />
          <main style={{ flex: 1, overflow: "auto", padding: "28px 32px" }}>
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
