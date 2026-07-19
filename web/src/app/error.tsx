"use client";

import { useEffect } from "react";

import { StatePanel } from "@/components/domain";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("authorized-ui-error", { digest: error.digest });
  }, [error]);
  return (
    <div>
      <StatePanel
        title="Não foi possível carregar esta visão"
        detail="A falha foi correlacionada sem registrar conteúdo confidencial."
      />
      <button className="button" onClick={reset} style={{ marginTop: 12 }}>
        Tentar novamente
      </button>
    </div>
  );
}
