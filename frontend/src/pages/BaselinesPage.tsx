import {
  Badge,
  Card,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { useState } from "react";
import { api, type Baseline, type BaselineDetail } from "../api";
import { useFetch } from "../components/shared";

const LEVEL_LABELS: Record<string, string> = {
  low: "NIST Low",
  moderate: "NIST Moderate",
  high: "NIST High",
  nd_confidential: "НД ТЗІ — Конфіденційна",
  nd_service: "НД ТЗІ — Службова",
  custom: "Власний",
};

const LEVEL_COLORS: Record<string, string> = {
  low: "green",
  moderate: "yellow",
  high: "red",
  nd_confidential: "violet",
  nd_service: "indigo",
  custom: "gray",
};

export default function BaselinesPage() {
  const { data: baselines } = useFetch<Baseline[]>("/baselines");
  const [detail, setDetail] = useState<BaselineDetail | null>(null);

  async function openDetail(id: number) {
    const { data } = await api.get<BaselineDetail>(`/baselines/${id}`);
    setDetail(data);
  }

  return (
    <>
      <Title order={2} mb="md">
        Базові набори (baselines)
      </Title>
      <Text c="dimmed" size="sm" mb="md">
        Набори контролів каталогу, що відповідають рівню впливу або базовому профілю
        НД ТЗІ. На їх основі формується цільовий профіль ІКС.
      </Text>

      {!baselines ? (
        <Loader />
      ) : (
        <Stack>
          {baselines.map((b) => (
            <Card
              key={b.id}
              withBorder
              padding="sm"
              style={{ cursor: "pointer" }}
              onClick={() => void openDetail(b.id)}
            >
              <Group justify="space-between">
                <Group>
                  <Badge color={LEVEL_COLORS[b.level] ?? "gray"} variant="light">
                    {LEVEL_LABELS[b.level] ?? b.level}
                  </Badge>
                  <Text fw={500}>{b.name}</Text>
                </Group>
                <Text size="sm" c="dimmed">
                  {b.item_count} заходів
                </Text>
              </Group>
              {b.description && (
                <Text size="sm" c="dimmed" mt={4}>
                  {b.description}
                </Text>
              )}
            </Card>
          ))}
          {baselines.length === 0 && <Text c="dimmed">Базових наборів ще немає.</Text>}
        </Stack>
      )}

      <Modal
        opened={detail !== null}
        onClose={() => setDetail(null)}
        title={detail?.name ?? ""}
        size="lg"
      >
        {detail && (
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={120}>Код</Table.Th>
                <Table.Th>Назва</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {detail.items.map((r) => (
                <Table.Tr key={r.id}>
                  <Table.Td>{r.code}</Table.Td>
                  <Table.Td>{r.title}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Modal>
    </>
  );
}
