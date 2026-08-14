"use client";

import { useCallback, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { bffFetch, queryKeys } from "@/lib/api-client";

interface PolicyAlert {
  id: string;
  title: string;
  severity: string;
  fired_at: string;
  acknowledged_at: string | null;
}

export function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const { data: alerts } = useQuery({
    queryKey: queryKeys.policyAlerts(),
    queryFn: () => bffFetch<PolicyAlert[]>("/api/v1/policy/alerts?status=active"),
    refetchInterval: 30_000,
  });

  const unreadCount = alerts?.filter((a) => !a.acknowledged_at).length ?? 0;

  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);

  const close = useCallback(() => {
    setIsOpen(false);
    buttonRef.current?.focus();
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        close();
      }
    },
    [isOpen, close],
  );

  return (
    <div className="relative" onKeyDown={handleKeyDown}>
      <button
        ref={buttonRef}
        className="icon-button"
        onClick={toggle}
        type="button"
        aria-label={`Notificações (${unreadCount} não lidas)`}
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <Bell size={15} />
        {unreadCount > 0 && (
          <span
            className="badge"
            style={{
              position: "absolute",
              top: -4,
              right: -4,
              minWidth: 16,
              height: 16,
              padding: "0 4px",
              fontSize: 10,
              lineHeight: "16px",
              borderRadius: "50%",
              background: "var(--red)",
              color: "#fff",
              textAlign: "center",
            }}
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <>
          <div
            style={{ position: "fixed", inset: 0, zIndex: 40 }}
            onClick={close}
            aria-hidden="true"
          />
          <div
            ref={panelRef}
            role="menu"
            aria-label="Notificações"
            style={{
              position: "absolute",
              right: 0,
              top: "100%",
              marginTop: 8,
              width: 320,
              maxHeight: 384,
              overflowY: "auto",
              background: "var(--surface)",
              border: "1px solid var(--line)",
              borderRadius: "var(--radius)",
              boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
              zIndex: 50,
            }}
          >
            <div
              style={{
                padding: "12px 16px",
                borderBottom: "1px solid var(--line)",
                fontWeight: 600,
                fontSize: 14,
              }}
            >
              Notificações
            </div>
            {alerts?.map((alert) => (
              <div
                key={alert.id}
                role="menuitem"
                style={{
                  padding: "12px 16px",
                  borderBottom: "1px solid var(--line)",
                  opacity: alert.acknowledged_at ? 0.6 : 1,
                }}
              >
                <div style={{ fontWeight: 500, fontSize: 13 }}>{alert.title}</div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginTop: 4,
                    fontSize: 12,
                    color: "var(--muted)",
                  }}
                >
                  <span>{alert.severity}</span>
                  <span>{new Date(alert.fired_at).toLocaleString("pt-BR")}</span>
                </div>
              </div>
            ))}
            {(!alerts || alerts.length === 0) && (
              <div
                style={{
                  padding: "24px 16px",
                  textAlign: "center",
                  color: "var(--muted)",
                  fontSize: 13,
                }}
              >
                Sem notificações
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
