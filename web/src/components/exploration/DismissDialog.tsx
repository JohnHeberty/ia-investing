"use client";

import { XCircle } from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";

export function DismissDialog({
  open,
  onOpenChange,
  dismissReason,
  onDismissReasonChange,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  dismissReason: string;
  onDismissReasonChange: (value: string) => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 50 }}
        />
        <Dialog.Content
          style={{
            position: "fixed",
            top: "50%",
            left: "50%",
            transform: "translate(-50%,-50%)",
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: 10,
            padding: 24,
            width: "min(480px, 90vw)",
            zIndex: 51,
          }}
        >
          <Dialog.Title style={{ fontSize: 16, fontWeight: 600, color: "var(--text)" }}>
            Dispensar sugestão
          </Dialog.Title>
          <Dialog.Description style={{ marginTop: 8, fontSize: 14, color: "var(--muted)" }}>
            Informe o motivo da dispensa. Esta justificativa será registrada na auditoria.
          </Dialog.Description>
          <textarea
            value={dismissReason}
            onChange={(e) => onDismissReasonChange(e.target.value)}
            placeholder="Ex: fora do perfil, risco elevado, dados insuficientes..."
            rows={4}
            className="form-input section-gap"
            style={{
              width: "100%",
              resize: "vertical",
            }}
          />
          <div className="section-gap flex justify-between" style={{ gap: 12 }}>
            <Dialog.Close asChild>
              <button
                style={{
                  borderRadius: 8,
                  border: "1px solid var(--line)",
                  padding: "8px 16px",
                  fontSize: 14,
                  color: "var(--muted)",
                  background: "none",
                  cursor: "pointer",
                }}
              >
                Cancelar
              </button>
            </Dialog.Close>
            <button
              onClick={onConfirm}
              disabled={!dismissReason.trim()}
              style={{
                borderRadius: 8,
                background: "var(--red)",
                padding: "8px 16px",
                fontSize: 14,
                fontWeight: 500,
                color: "#fff",
                border: "none",
                cursor: "pointer",
                opacity: dismissReason.trim() ? 1 : 0.5,
              }}
            >
              Dispensar
            </button>
          </div>
          <Dialog.Close asChild>
            <button
              aria-label="Fechar"
              style={{
                position: "absolute",
                top: 12,
                right: 12,
                background: "none",
                border: "none",
                color: "var(--muted)",
                cursor: "pointer",
              }}
            >
              <XCircle size={18} />
            </button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
