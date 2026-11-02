"use client";

// "/" sends a logged-in user to their landing page (the DPO to the review queue, a product manager to the
// assistant: separation of duties) and everyone else to the login form.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { landing } from "@/lib/nav";
import type { User } from "@/lib/types";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    api.get<User>("/api/auth/me").then((u) => router.replace(landing(u))).catch(() => router.replace("/login"));
  }, [router]);
  return null;
}
