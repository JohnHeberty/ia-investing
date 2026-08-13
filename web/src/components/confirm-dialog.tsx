"use client";

import * as Dialog from "@radix-ui/react-dialog";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => void;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirmar",
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            zIndex: 1000,
          }}
        />
        <Dialog.Content
          style={{
            position: "fixed",
            top: "50%",
            left: "50%",
            transform: "translate(-50%,-50%)",
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: 12,
            padding: 24,
            zIndex: 1001,
            maxWidth: 400,
            width: "90%",
          }}
        >
          <Dialog.Title style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>{title}</Dialog.Title>
          <Dialog.Description
            style={{ fontSize: 13, color: "var(--muted)", marginTop: 8, lineHeight: 1.5 }}
          >
            {description}
          </Dialog.Description>
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 20 }}>
            <Dialog.Close asChild>
              <button className="button secondary" type="button">
                Cancelar
              </button>
            </Dialog.Close>
            <Dialog.Close asChild>
              <button className="button" type="button" onClick={onConfirm}>
                {confirmLabel}
              </button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
