export type ColDef = { key: string; label: string; fmt?: (v: unknown) => string };

export function LabeledTable({ data, columns }: { data: Record<string, unknown>[]; columns: ColDef[] }) {
  if (data.length === 0) {
    return <p className="text-xs text-text-4 py-2">데이터 없음</p>;
  }
  return (
    <div className="overflow-x-auto rounded-lg bg-surface shadow-card">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="bg-surface-muted border-b border-border">
            {columns.map((c) => (
              <th key={c.key} className="px-2.5 py-2 text-left text-text-3 font-normal whitespace-nowrap">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="border-b border-border last:border-0">
              {columns.map((c) => {
                const v = row[c.key];
                const display = c.fmt ? c.fmt(v) : (v == null || v === "" ? "-" : String(v));
                return (
                  <td key={c.key} className="px-2.5 py-2 text-text-2 whitespace-nowrap">
                    {display}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
