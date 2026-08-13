"use client";

import { StatePanel } from "@/components/domain";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div>
      <StatePanel
        title="Não foi possível carregar esta visão"
        detail={error.digest ? `Falha correlacionada: ${error.digest}` : error.message}
      />
      <button className="button" onClick={reset} style={{ marginTop: 12 }}>
        Tentar novamente
      </button>
    </div>
  );
}
