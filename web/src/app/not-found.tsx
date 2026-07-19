import { StatePanel } from "@/components/domain";

export default function NotFound() {
  return (
    <StatePanel
      title="Recurso não encontrado"
      detail="O recurso não existe ou não está visível para sua organização."
    />
  );
}
