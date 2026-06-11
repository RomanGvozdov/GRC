import { Badge, Table, Text } from "@mantine/core";
import { useCallback, useEffect, useState } from "react";
import { api, type ImplStatus, type RiskLevel } from "../api";
import { IMPL_COLORS, IMPL_LABELS, LEVEL_COLORS, LEVEL_LABELS, scoreLevel } from "../labels";

/** Простий хук завантаження даних з /api з ручним перезавантаженням. */
export function useFetch<T>(url: string, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get<T>(url)
      .then(({ data: result }) => {
        if (!cancelled) setData(result);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, version, ...deps]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { data, loading, reload };
}

export function LevelBadge({ score }: { score: number | null }) {
  const level: RiskLevel | null = scoreLevel(score);
  if (!level || score === null) return <Text c="dimmed">—</Text>;
  return (
    <Badge color={LEVEL_COLORS[level]} variant="filled">
      {score} · {LEVEL_LABELS[level]}
    </Badge>
  );
}

export function ImplBadge({ status }: { status: ImplStatus }) {
  return (
    <Badge color={IMPL_COLORS[status]} variant="light">
      {IMPL_LABELS[status]}
    </Badge>
  );
}

export function EmptyRow({ colSpan, text }: { colSpan: number; text?: string }) {
  return (
    <Table.Tr>
      <Table.Td colSpan={colSpan}>
        <Text c="dimmed" ta="center" py="md">
          {text ?? "Немає записів"}
        </Text>
      </Table.Td>
    </Table.Tr>
  );
}
