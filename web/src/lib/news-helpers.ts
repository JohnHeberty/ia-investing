export function directionTone(hint: string | null): "good" | "bad" | "neutral" {
  if (hint === "positive") return "good";
  if (hint === "negative") return "bad";
  return "neutral";
}

export function effectTone(effect: string | null): "good" | "bad" | "neutral" {
  if (effect === "strengthen") return "good";
  if (effect === "weaken") return "bad";
  return "neutral";
}
