"use client";

import { useState, useCallback, useEffect } from "react";
import { X, CheckCircle, AlertTriangle } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";

import { bffFetch, queryKeys } from "@/lib/api-client";

const newCaseSchema = z.object({
  title: z.string().min(3, "Título deve ter pelo menos 3 caracteres"),
  instrument: z.string().min(1, "Instrumento é obrigatório"),
  case_type: z.enum(["fundamental", "macro", "event", "technical"], {
    error: "Selecione um tipo de caso",
  }),
});

type NewCaseFormValues = z.infer<typeof newCaseSchema>;

export function CreateCaseForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  useEffect(() => {
    if (!submitSuccess) return;
    const timer = setTimeout(() => {
      onClose();
      setSubmitSuccess(false);
    }, 1500);
    return () => clearTimeout(timer);
  }, [submitSuccess, onClose]);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<NewCaseFormValues>({
    defaultValues: { title: "", instrument: "", case_type: undefined },
  });

  const onSubmit = useCallback(
    async (values: NewCaseFormValues) => {
      setSubmitError(null);
      setSubmitSuccess(false);

      const idempotencyKey =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

      try {
        const existingCases = queryClient.getQueryData(
          queryKeys.researchCases(),
        ) as Array<Record<string, unknown>> | undefined;

        const duplicate = existingCases?.find(
          (c) =>
            String(c.instrument_id ?? "").toLowerCase() ===
            values.instrument.toLowerCase(),
        );

        if (duplicate) {
          setSubmitError(
            `Já existe um caso para o instrumento "${values.instrument}". Caso existente: ${String(duplicate.title ?? "Sem título")}`,
          );
          return;
        }

        const result = await bffFetch<{ id: string }>("/api/v1/research/cases", {
          method: "POST",
          headers: { "X-Idempotency-Key": idempotencyKey },
          body: JSON.stringify({
            title: values.title,
            instrument_id: values.instrument,
            case_type: values.case_type,
            priority: "medium",
            state: "open",
          }),
        });

        if (!result?.id) {
          throw new Error("Erro ao criar caso");
        }

        setSubmitSuccess(true);
        queryClient.invalidateQueries({ queryKey: queryKeys.researchCases() });
      } catch (err) {
        setSubmitError(
          err instanceof Error ? err.message : "Erro desconhecido",
        );
      }
    },
    [queryClient, onClose],
  );

  return (
    <section
      className="card card-pad section-gap"
      aria-label="Abrir novo caso de pesquisa"
    >
      <div className="card-title">
        <h2>Novo caso de pesquisa</h2>
        <button
          onClick={onClose}
          className="icon-button"
          aria-label="Fechar formulário"
          style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}
        >
          <X size={16} />
        </button>
      </div>

      {submitSuccess ? (
        <div
          role="status"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "12px 16px",
            background: "var(--accent-soft)",
            borderRadius: 8,
            color: "var(--accent)",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          <CheckCircle size={16} />
          Caso criado com sucesso
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label
                htmlFor="case-title"
                style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}
              >
                Título <span aria-hidden="true" style={{ color: "var(--red)" }}>*</span>
              </label>
              <input
                id="case-title"
                type="text"
                aria-required="true"
                aria-invalid={!!errors.title}
                aria-describedby={errors.title ? "case-title-error" : undefined}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "var(--surface-2)",
                  border: `1px solid ${errors.title ? "var(--red)" : "var(--line)"}`,
                  borderRadius: 8,
                  color: "var(--text)",
                  fontSize: 13,
                }}
                placeholder="Ex: Valuation Petrobras PBR"
                {...register("title")}
              />
              {errors.title && (
                <p id="case-title-error" role="alert" style={{ color: "var(--red)", fontSize: 11, marginTop: 4 }}>
                  {errors.title.message}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="case-instrument"
                style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}
              >
                Instrumento <span aria-hidden="true" style={{ color: "var(--red)" }}>*</span>
              </label>
              <input
                id="case-instrument"
                type="text"
                aria-required="true"
                aria-invalid={!!errors.instrument}
                aria-describedby={errors.instrument ? "case-instrument-error" : undefined}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "var(--surface-2)",
                  border: `1px solid ${errors.instrument ? "var(--red)" : "var(--line)"}`,
                  borderRadius: 8,
                  color: "var(--text)",
                  fontSize: 13,
                }}
                placeholder="Ex: PETR4, USD/BRL"
                {...register("instrument")}
              />
              {errors.instrument && (
                <p id="case-instrument-error" role="alert" style={{ color: "var(--red)", fontSize: 11, marginTop: 4 }}>
                  {errors.instrument.message}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="case-type"
                style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}
              >
                Tipo de caso <span aria-hidden="true" style={{ color: "var(--red)" }}>*</span>
              </label>
              <select
                id="case-type"
                aria-required="true"
                aria-invalid={!!errors.case_type}
                aria-describedby={errors.case_type ? "case-type-error" : undefined}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "var(--surface-2)",
                  border: `1px solid ${errors.case_type ? "var(--red)" : "var(--line)"}`,
                  borderRadius: 8,
                  color: "var(--text)",
                  fontSize: 13,
                }}
                {...register("case_type")}
              >
                <option value="">Selecione...</option>
                <option value="fundamental">Fundamental</option>
                <option value="macro">Macro</option>
                <option value="event">Evento corporativo</option>
                <option value="technical">Técnico</option>
              </select>
              {errors.case_type && (
                <p id="case-type-error" role="alert" style={{ color: "var(--red)", fontSize: 11, marginTop: 4 }}>
                  {errors.case_type.message}
                </p>
              )}
            </div>

            {submitError && (
              <div
                role="alert"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 14px",
                  background: "rgb(255 133 127 / 10%)",
                  border: "1px solid rgb(255 133 127 / 30%)",
                  borderRadius: 8,
                  color: "var(--red)",
                  fontSize: 12,
                }}
              >
                <AlertTriangle size={14} />
                {submitError}
              </div>
            )}

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={onClose}
                className="button secondary"
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="button"
                disabled={isSubmitting}
                aria-label="Criar caso de pesquisa"
                style={{ opacity: isSubmitting ? 0.6 : 1 }}
              >
                {isSubmitting ? "Criando..." : "Criar caso"}
              </button>
            </div>
          </div>
        </form>
      )}
    </section>
  );
}
