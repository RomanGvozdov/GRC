import {
  Anchor,
  Badge,
  Card,
  Grid,
  Group,
  Loader,
  Progress,
  SimpleGrid,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { Link } from "react-router-dom";
import type { Dashboard } from "../api";
import { LevelBadge, useFetch } from "../components/shared";
import { useSystem, withSystem } from "../systemContext";
import { LEVEL_COLORS, LEVEL_LABELS, RISK_STATUS_LABELS } from "../labels";

function heatColor(likelihood: number, impact: number): string {
  const score = likelihood * impact;
  if (score <= 4) return "var(--mantine-color-green-2)";
  if (score <= 9) return "var(--mantine-color-yellow-2)";
  if (score <= 14) return "var(--mantine-color-orange-3)";
  return "var(--mantine-color-red-3)";
}

function HeatMap({ cells }: { cells: Dashboard["heat_map"] }) {
  const counts = new Map(cells.map((c) => [`${c.likelihood}-${c.impact}`, c.count]));
  return (
    <Table withTableBorder withColumnBorders w="auto">
      <Table.Tbody>
        {[5, 4, 3, 2, 1].map((impact) => (
          <Table.Tr key={impact}>
            <Table.Td>
              <Text size="xs" fw={700}>
                Вплив {impact}
              </Text>
            </Table.Td>
            {[1, 2, 3, 4, 5].map((likelihood) => {
              const count = counts.get(`${likelihood}-${impact}`) ?? 0;
              return (
                <Table.Td
                  key={likelihood}
                  style={{
                    background: heatColor(likelihood, impact),
                    width: 56,
                    height: 44,
                    textAlign: "center",
                  }}
                >
                  {count > 0 && <Text fw={700}>{count}</Text>}
                </Table.Td>
              );
            })}
          </Table.Tr>
        ))}
        <Table.Tr>
          <Table.Td />
          {[1, 2, 3, 4, 5].map((likelihood) => (
            <Table.Td key={likelihood} style={{ textAlign: "center" }}>
              <Text size="xs" fw={700}>
                Йм. {likelihood}
              </Text>
            </Table.Td>
          ))}
        </Table.Tr>
      </Table.Tbody>
    </Table>
  );
}

function StatCard({ label, value, danger }: { label: string; value: number; danger?: boolean }) {
  return (
    <Card withBorder padding="md">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text size="xl" fw={700} c={danger && value > 0 ? "red" : undefined}>
        {value}
      </Text>
    </Card>
  );
}

export default function DashboardPage() {
  const { systemId } = useSystem();
  const { data } = useFetch<Dashboard>(withSystem("/dashboard", systemId), [systemId]);
  if (!data) return <Loader />;

  return (
    <>
      <Title order={2} mb="md">
        Дашборд
      </Title>
      <SimpleGrid cols={{ base: 2, md: 5 }} mb="md">
        <StatCard label="Усього ризиків" value={data.risks_total} />
        <StatCard label="Прострочені перегляди ризиків" value={data.overdue_risk_reviews} danger />
        <StatCard
          label="Прострочені перевірки контролів"
          value={data.overdue_control_reviews}
          danger
        />
        <StatCard label="Прострочені дії з обробки" value={data.overdue_actions} danger />
        <StatCard
          label="Прострочені перегляди політик"
          value={data.overdue_policy_reviews}
          danger
        />
      </SimpleGrid>

      <Grid>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Card withBorder padding="md">
            <Title order={4} mb="sm">
              Карта ризиків (залишкова оцінка)
            </Title>
            <HeatMap cells={data.heat_map} />
            <Group mt="sm" gap="xs">
              {(Object.keys(LEVEL_LABELS) as (keyof typeof LEVEL_LABELS)[]).map((level) => (
                <Badge key={level} color={LEVEL_COLORS[level]} variant="light">
                  {LEVEL_LABELS[level]}: {data.risks_by_level[level] ?? 0}
                </Badge>
              ))}
              <Badge color="gray" variant="light">
                Без оцінки: {data.risks_by_level.unassessed ?? 0}
              </Badge>
            </Group>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 6 }}>
          <Card withBorder padding="md" mb="md">
            <Title order={4} mb="sm">
              Відповідність фреймворкам
            </Title>
            {data.frameworks.map((row) => (
              <div key={row.framework.id} style={{ marginBottom: 12 }}>
                <Group justify="space-between" mb={4}>
                  <Text size="sm">
                    {row.framework.name}
                    {row.framework.version ? ` (${row.framework.version})` : ""}
                  </Text>
                  <Text size="sm" fw={700}>
                    {row.coverage_percent}% ({row.covered}/{row.total})
                  </Text>
                </Group>
                <Progress value={row.coverage_percent} />
              </div>
            ))}
          </Card>

          <Card withBorder padding="md">
            <Title order={4} mb="sm">
              Топ ризиків
            </Title>
            <Table>
              <Table.Tbody>
                {data.top_risks.map((risk) => (
                  <Table.Tr key={risk.id}>
                    <Table.Td>
                      <Anchor component={Link} to={`/risks/${risk.id}`} size="sm">
                        {risk.code} — {risk.title}
                      </Anchor>
                    </Table.Td>
                    <Table.Td>
                      <LevelBadge score={risk.residual_score} />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>
        </Grid.Col>
      </Grid>

      <Card withBorder padding="md" mt="md">
        <Title order={4} mb="sm">
          Ризики за статусами
        </Title>
        <Group>
          {Object.entries(RISK_STATUS_LABELS).map(([status, label]) => (
            <Badge key={status} variant="outline">
              {label}: {data.risks_by_status[status] ?? 0}
            </Badge>
          ))}
        </Group>
      </Card>
    </>
  );
}
