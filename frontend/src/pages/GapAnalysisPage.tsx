import {
  Anchor,
  Badge,
  Card,
  Group,
  Loader,
  Progress,
  Select,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Framework, GapSummary } from "../api";
import { EmptyRow, ImplBadge, useFetch } from "../components/shared";
import { useSystem, withSystem } from "../systemContext";
import { COVERAGE_COLORS, COVERAGE_LABELS } from "../labels";

export default function GapAnalysisPage() {
  const { data: frameworks } = useFetch<Framework[]>("/frameworks");
  const [frameworkId, setFrameworkId] = useState<string | null>(null);

  useEffect(() => {
    if (frameworks?.length && !frameworkId) setFrameworkId(String(frameworks[0].id));
  }, [frameworks, frameworkId]);

  const { systemId } = useSystem();
  const { data: gap } = useFetch<GapSummary | null>(
    frameworkId
      ? withSystem(`/frameworks/${frameworkId}/gap-analysis`, systemId)
      : "/frameworks",
    [frameworkId, systemId],
  );
  const summary = frameworkId && gap && "coverage_percent" in gap ? (gap as GapSummary) : null;

  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  function toggle(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Gap-аналіз</Title>
        <Select
          data={frameworks?.map((f) => ({ value: String(f.id), label: f.name })) ?? []}
          value={frameworkId}
          onChange={setFrameworkId}
          w={320}
        />
      </Group>

      {!summary ? (
        <Loader />
      ) : (
        <>
          <Card withBorder padding="md" mb="md">
            <Group justify="space-between" mb="xs">
              <Text fw={600}>
                {summary.framework.name}
                {summary.framework.version ? ` (${summary.framework.version})` : ""}
              </Text>
              <Text fw={700}>{summary.coverage_percent}% відповідності</Text>
            </Group>
            <Progress value={summary.coverage_percent} size="lg" mb="sm" />
            <Group gap="xs">
              <Badge color="green" variant="light">
                Покрито: {summary.covered}
              </Badge>
              <Badge color="yellow" variant="light">
                Частково: {summary.partial}
              </Badge>
              <Badge color="red" variant="light">
                Не покрито: {summary.not_covered}
              </Badge>
              <Badge color="gray" variant="light">
                Не застосовно: {summary.not_applicable}
              </Badge>
            </Group>
          </Card>

          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={100}>Код</Table.Th>
                <Table.Th>Вимога</Table.Th>
                <Table.Th w={140}>Покриття</Table.Th>
                <Table.Th>Контролі</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {summary.requirements.length === 0 && <EmptyRow colSpan={4} />}
              {summary.requirements.map((row) => {
                const isOpen = expanded.has(row.requirement.id);
                const desc = row.requirement.description;
                return (
                  <>
                    <Table.Tr
                      key={row.requirement.id}
                      style={{ cursor: desc ? "pointer" : "default" }}
                      onClick={() => desc && toggle(row.requirement.id)}
                    >
                      <Table.Td>
                        {desc ? (isOpen ? "▾ " : "▸ ") : ""}
                        {row.requirement.code}
                      </Table.Td>
                      <Table.Td>{row.requirement.title}</Table.Td>
                      <Table.Td>
                        <Badge color={COVERAGE_COLORS[row.coverage]} variant="light">
                          {COVERAGE_LABELS[row.coverage]}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Group gap="xs">
                          {row.controls.map((control) => (
                            <Group key={control.id} gap={4}>
                              <Anchor component={Link} to={`/controls/${control.id}`} size="sm">
                                {control.code}
                              </Anchor>
                              {control.status && <ImplBadge status={control.status} />}
                            </Group>
                          ))}
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                    {isOpen && desc && (
                      <Table.Tr key={`${row.requirement.id}-desc`}>
                        <Table.Td colSpan={4}>
                          <Text size="sm" c="dimmed" style={{ whiteSpace: "pre-wrap" }} pl="md">
                            {desc}
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    )}
                  </>
                );
              })}
            </Table.Tbody>
          </Table>
        </>
      )}
    </>
  );
}
