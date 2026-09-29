export type SymbolMatch = {
  id: string;
  score: number;
  metadata?: Record<string, unknown>;
};

export type RankedSymbol = {
  id: string;
  score: number;
  library: string;
  short_name: string;
  number: string;
  variant_id: string;
  description: string;
  duplicate_count: number;
  source_rows: number[];
};

function field(metadata: Record<string, unknown> | undefined, name: string): string {
  const value = metadata?.[name];
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

export function distinctSymbols(raw: SymbolMatch[], topK: number): RankedSymbol[] {
  const found = new Map<string, RankedSymbol>();
  for (const item of [...raw].sort((a, b) => b.score - a.score)) {
    const library = field(item.metadata, "library");
    const short_name = field(item.metadata, "short_name");
    const number = field(item.metadata, "number");
    const variant_id = field(item.metadata, "variant_id");
    const identity = short_name || number
      ? JSON.stringify([library, number, short_name, variant_id])
      : item.id;
    const existing = found.get(identity);
    if (existing) {
      existing.duplicate_count++;
      const row = item.metadata?.row;
      if (typeof row === "number") existing.source_rows.push(row);
      continue;
    }
    const row = item.metadata?.row;
    found.set(identity, {
      id: item.id,
      score: item.score,
      library,
      short_name,
      number,
      variant_id,
      description: field(item.metadata, "description"),
      duplicate_count: 1,
      source_rows: typeof row === "number" ? [row] : [],
    });
  }
  return [...found.values()].slice(0, topK);
}
