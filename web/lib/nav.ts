import type { User } from "@/lib/types";

/** The DPO lands on the review queue and has no Assistant page (separation of duties); a product manager on the assistant. */
export const landing = (u: User) => (u.role === "dpo" ? "/review" : "/assistant");

export const pagesFor = (u: User): { href: string; label: string }[] =>
  u.role === "dpo"
    ? [{ href: "/review", label: "DPO review queue" }, { href: "/register", label: "Register" }, { href: "/memory", label: "Memory" }]
    : [{ href: "/assistant", label: "Assistant" }, { href: "/register", label: "Register" }, { href: "/memory", label: "Memory" }];
