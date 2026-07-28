import { csrfHeaders } from "./csrf";

export function commandHeaders(idempotencyKey: string): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-Idempotency-Key": idempotencyKey,
    "X-Organization-Id": process.env.NEXT_PUBLIC_ORGANIZATION_ID ?? "",
    ...csrfHeaders(),
  };
}
