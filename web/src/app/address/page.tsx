"use client";

import PageHeader from "@/components/PageHeader";
import AddressSearchForm from "@/components/AddressSearchForm";

export default function AddressPage() {
  return (
    <div>
      <PageHeader
        title="Address Lookup"
        description="Check a Bitcoin address for risk, OFAC exposure, entity membership, and graph context."
      />

      <div className="card">
        <AddressSearchForm />
      </div>
    </div>
  );
}
