import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  Progress,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  errorText,
  type Assessment,
  type AssessmentDetail,
  type AssessmentResult,
  type ConMonHealth,
  type Profile,
} from "../api";
import { useFetch } from "../components/shared";
import { useSystem } from "../systemContext";

const STATUS_LABELS: Record<string, string> = {
  planned: "Заплановано",
  in_progress: "Триває",
  completed: "Завершено",
};
const RESULT_LABELS: Record<string, string> = {
  not_assessed: "Не оцінено",
  satisfied: "Задоволено",
  other_than_satisfied: "Не задоволено",
};
const RESULT_COLORS: Record<string, string> = {
  not_assessed: "gray",
  satisfied: "green",
  other_than_satisfied: "red",
};

export default function AssessmentPage() {
  const { systemId } = useSystem();
  const listUrl = systemId ? `/systems/${systemId}/assessments` : "/baselines";
  const { data: assessments, reload } = useFetch<Assessment[]>(listUrl, [systemId]);
  const healthUrl = systemId ? `/systems/${systemId}/conmon/health` : "/baselines";
  const { data: health, reload: reloadHealth } = useFetch<ConMonHealth>(healthUrl, [systemId]);
  const profilesUrl = systemId ? `/systems/${systemId}/profiles` : "/baselines";
  const { data: profiles } = useFetch<Profile[]>(profilesUrl, [systemId]);

  const [detail, setDetail] = useState<AssessmentDetail | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  const [genOpen, setGenOpen] = useState(false);
  const [genProfile, setGenProfile] = useState<string | null>(null);
  const [genTitle, setGenTitle] = useState("");

  const [noteCtl, setNoteCtl] = useState<AssessmentResult | null>(null);
  const [noteText, setNoteText] = useState("");

  const loadDetail = useCallback(async (id: number) => {
    const { data } = await api.get<AssessmentDetail>(`/assessments/${id}`);
    setDetail(data);
  }, []);

  useEffect(() => {
    setDetail(null);
  }, [systemId]);

  async function generate() {
    if (!systemId || !genProfile) return;
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<AssessmentDetail>(`/systems/${systemId}/assessments`, {
        profile_id: Number(genProfile),
        title: genTitle || null,
      });
      setGenOpen(false);
      setGenProfile(null);
      setGenTitle("");
      reload();
      setDetail(data);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function setResult(ctl: AssessmentResult, result: string, notes?: string) {
    if (!detail) return;
    try {
      await api.put(`/assessments/${detail.id}/results/${ctl.requirement.id}`, {
        result,
        notes: notes ?? ctl.notes ?? null,
      });
      await loadDetail(detail.id);
      reload();
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function complete() {
    if (!detail) return;
    await api.patch(`/assessments/${detail.id}`, { status: "completed" });
    await loadDetail(detail.id);
    reload();
  }

  async function toPoam() {
    if (!detail) return;
    setBusy(true);
    try {
      const { data } = await api.post<{ created: number; skipped: number }>(
        `/assessments/${detail.id}/to-poam`,
      );
      setInfo(`Створено пунктів POA&M: ${data.created}, пропущено: ${data.skipped}`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  if (!systemId) {
    return (
      <>
        <Title order={2} mb="md">
          Оцінювання та моніторинг
        </Title>
        <Alert color="blue" variant="light">
          Оберіть конкретну ІКС у перемикачі вгорі.
        </Alert>
      </>
    );
  }

  const list = systemId ? (assessments as Assessment[] | null) : null;
  const hp = systemId ? (health as ConMonHealth | null) : null;

  return (
    <>
      <Title order={2} mb="md">
        Оцінювання та моніторинг
      </Title>
      {error && (
        <Alert color="red" mb="md" onClose={() => setError("")} withCloseButton>
          {error}
        </Alert>
      )}
      {info && (
        <Alert color="green" mb="md" onClose={() => setInfo("")} withCloseButton>
          {info}
        </Alert>
      )}

      {/* Безперервний моніторинг (ConMon) */}
      <Card withBorder mb="lg">
        <Group justify="space-between" mb="xs">
          <Title order={4}>Здоров'я контролів (ConMon)</Title>
          <Button size="xs" variant="subtle" onClick={() => reloadHealth()}>
            Оновити
          </Button>
        </Group>
        {!hp ? (
          <Loader size="sm" />
        ) : hp.total === 0 ? (
          <Text c="dimmed" size="sm">
            Немає профілю для моніторингу. Згенеруйте цільовий профіль ІКС.
          </Text>
        ) : (
          <>
            <SimpleGrid cols={4} mb="sm">
              <div>
                <Text size="xl" fw={700}>{hp.total}</Text>
                <Text size="xs" c="dimmed">контролів</Text>
              </div>
              <div>
                <Text size="xl" fw={700} c="green">{hp.fresh}</Text>
                <Text size="xs" c="dimmed">свіжі докази</Text>
              </div>
              <div>
                <Text size="xl" fw={700} c="orange">{hp.stale}</Text>
                <Text size="xs" c="dimmed">прострочені (дрейф)</Text>
              </div>
              <div>
                <Text size="xl" fw={700} c="red">{hp.none}</Text>
                <Text size="xs" c="dimmed">без доказів</Text>
              </div>
            </SimpleGrid>
            <Progress.Root size="lg">
              <Progress.Section value={(hp.fresh / hp.total) * 100} color="green" />
              <Progress.Section value={(hp.stale / hp.total) * 100} color="orange" />
              <Progress.Section value={(hp.none / hp.total) * 100} color="red" />
            </Progress.Root>
            {hp.drift.length > 0 && (
              <Text size="sm" c="dimmed" mt="xs">
                Дрейф: {hp.drift.map((d) => d.code).join(", ")}
              </Text>
            )}
            <Text size="xs" c="dimmed" mt="xs">
              Авто-докази надсилають сканери/CIS через <code>POST /api/ingest/evidence</code>{" "}
              за API-токеном (доступ «контролі: запис»).
            </Text>
          </>
        )}
      </Card>

      <Group justify="space-between" mb="sm">
        <Title order={4}>Оцінювання (800-53A)</Title>
        <Button onClick={() => setGenOpen(true)}>Нове оцінювання</Button>
      </Group>

      <Group align="flex-start" gap="lg" wrap="nowrap">
        <Stack w={280} style={{ flexShrink: 0 }}>
          {!list ? (
            <Loader />
          ) : list.length === 0 ? (
            <Text c="dimmed">Оцінювань ще немає.</Text>
          ) : (
            list.map((a) => (
              <Card
                key={a.id}
                withBorder
                padding="sm"
                style={{
                  cursor: "pointer",
                  borderColor: a.id === detail?.id ? "var(--mantine-color-blue-5)" : undefined,
                }}
                onClick={() => void loadDetail(a.id)}
              >
                <Group justify="space-between">
                  <Text fw={500} size="sm">{a.title}</Text>
                  <Badge size="xs" variant="light">{STATUS_LABELS[a.status]}</Badge>
                </Group>
                <Text size="xs" c="dimmed" mt={4}>
                  ✓{a.satisfied} ✗{a.other_than_satisfied} ?{a.not_assessed}
                </Text>
              </Card>
            ))
          )}
        </Stack>

        <Stack style={{ flexGrow: 1, minWidth: 0 }}>
          {!detail ? (
            <Text c="dimmed">Оберіть оцінювання зліва.</Text>
          ) : (
            <>
              <Group justify="space-between">
                <Title order={4}>{detail.title}</Title>
                <Group gap="xs">
                  <Button size="xs" variant="default" onClick={() => void toPoam()} loading={busy}>
                    Не задоволені → POA&M
                  </Button>
                  {detail.status !== "completed" && (
                    <Button size="xs" color="green" onClick={() => void complete()}>
                      Завершити
                    </Button>
                  )}
                </Group>
              </Group>
              <Table striped>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th w={110}>Контроль</Table.Th>
                    <Table.Th>Назва</Table.Th>
                    <Table.Th w={190}>Результат</Table.Th>
                    <Table.Th w={90}>Нотатка</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {detail.results.map((r) => (
                    <Table.Tr key={r.id}>
                      <Table.Td>{r.requirement.code}</Table.Td>
                      <Table.Td>{r.requirement.title}</Table.Td>
                      <Table.Td>
                        <Select
                          size="xs"
                          data={Object.entries(RESULT_LABELS).map(([value, label]) => ({ value, label }))}
                          value={r.result}
                          onChange={(v) => v && void setResult(r, v)}
                          w={180}
                        />
                      </Table.Td>
                      <Table.Td>
                        <Button
                          size="compact-xs"
                          variant={r.notes ? "light" : "subtle"}
                          color={RESULT_COLORS[r.result]}
                          onClick={() => {
                            setNoteCtl(r);
                            setNoteText(r.notes ?? "");
                          }}
                        >
                          {r.notes ? "Є" : "—"}
                        </Button>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </>
          )}
        </Stack>
      </Group>

      <Modal opened={genOpen} onClose={() => setGenOpen(false)} title="Нове оцінювання з профілю">
        <Stack>
          <Select
            label="Профіль"
            data={profiles?.map((p) => ({ value: String(p.id), label: `${p.name} (v${p.version})` })) ?? []}
            value={genProfile}
            onChange={setGenProfile}
            required
          />
          <TextInput
            label="Назва"
            value={genTitle}
            onChange={(e) => setGenTitle(e.currentTarget.value)}
          />
          <Button onClick={() => void generate()} disabled={!genProfile} loading={busy}>
            Створити
          </Button>
        </Stack>
      </Modal>

      <Modal
        opened={noteCtl !== null}
        onClose={() => setNoteCtl(null)}
        title={noteCtl ? `Нотатка: ${noteCtl.requirement.code}` : ""}
      >
        <Stack>
          <Textarea
            value={noteText}
            onChange={(e) => setNoteText(e.currentTarget.value)}
            minRows={4}
            autosize
            label="Обґрунтування / деталі оцінки"
          />
          <Button
            onClick={() => {
              if (noteCtl) void setResult(noteCtl, noteCtl.result, noteText);
              setNoteCtl(null);
            }}
          >
            Зберегти
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
