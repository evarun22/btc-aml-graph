"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Overview" },
  { href: "/address", label: "Address" },
  { href: "/alerts", label: "Alerts" },
  { href: "/entities", label: "Entities" },
  { href: "/ofac", label: "OFAC" },
  { href: "/graph", label: "Graph" },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3">
        <Link href="/" className="text-sm font-semibold text-cyan-400">
          Bitcoin AML Graph
        </Link>

        <div className="flex flex-wrap items-center gap-4">
          {links.map((link) => {
            const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={
                  active
                    ? "text-sm font-medium text-cyan-400"
                    : "text-sm text-slate-300 hover:text-white"
                }
              >
                {link.label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
