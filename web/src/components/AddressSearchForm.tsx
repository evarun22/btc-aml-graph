"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function AddressSearchForm({
  initialAddress = "",
}: {
  initialAddress?: string;
}) {
  const router = useRouter();
  const [address, setAddress] = useState(initialAddress);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = address.trim();
    if (!trimmed) return;
    router.push(`/address/${encodeURIComponent(trimmed)}`);
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
      <input
        className="input"
        placeholder="Enter BTC address (bc1..., 1..., 3...)"
        value={address}
        onChange={(e) => setAddress(e.target.value)}
      />
      <button className="btn" type="submit">
        Check Address
      </button>
    </form>
  );
}
