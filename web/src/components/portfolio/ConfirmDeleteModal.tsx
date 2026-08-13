interface ConfirmDeleteModalProps {
  show: boolean;
  name: string;
  onClose: () => void;
  onConfirm: () => void;
  isPending: boolean;
  error?: Error | null;
}

export function ConfirmDeleteModal({
  show,
  name,
  onClose,
  onConfirm,
  isPending,
  error,
}: ConfirmDeleteModalProps) {
  if (!show) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="card card-pad modal-content" onClick={(e) => e.stopPropagation()}>
        <h3>Excluir Carteira</h3>
        <p className="mt-8">
          Tem certeza que deseja excluir <strong>{name}</strong>? Esta ação é irreversível. Todas as
          posições, transações e dados vinculados serão removidos permanentemente.
        </p>
        {error && (
          <div className="mt-8" style={{ fontSize: 12, color: "var(--red)" }}>
            {error.message || "Erro ao excluir"}
          </div>
        )}
        <div className="flex gap-8 mt-16" style={{ justifyContent: "flex-end" }}>
          <button className="button secondary" onClick={onClose} disabled={isPending}>
            Cancelar
          </button>
          <button className="button danger" disabled={isPending} onClick={onConfirm}>
            {isPending ? "Excluindo..." : "Excluir Carteira"}
          </button>
        </div>
      </div>
    </div>
  );
}
