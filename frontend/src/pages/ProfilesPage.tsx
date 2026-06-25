import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  Select,
  Stack,
  Table,
  Tabs,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  errorText,
  type Baseline,
  type Profile,
  type ProfileDetail,
  type Requirement,
  type ResolvedProfile,
} from "../api";
import { useFetch } from "../components/shared";
import { useSystem } from "../systemContext";

const STATUS_LABELS: Record<string, string> = {
  draft: "Чернетка",
  approved: "Затверджено",
  superseded: "Замінено",
};
const STATUS_COLORS: Record<string, string> = {
  draft: "blue",
  approved: "green",
  superseded: "gray",
};

export default function ProfilesPage() {
  const { systemId } = useSystem();
  const profilesUrl = systemId ? `/systems/${systemId}/profiles` : "/baselines";
  const { data: profiles, reload: reloadList } = useFetch<Profile[]>(profilesUrl, [systemId]);
  const { data: baselines } = useFetch<Baseline[]>("/baselines");

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [resolved, setResolved] = useState<ResolvedProfile | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Генерація
  const [genOpen, setGenOpen] = useState(false);
  const [genBaseline, setGenBaseline] = useState<string | null>(null);
  const [genName, setGenName] = useState("");

  // Tailoring
  const [tailorAction, setTailorAction] = useState<"add" | "remove" | null>(null);
  const [tailorRequirement, setTailorRequirement] = useState<number | null>(null);
  const [tailorJustification, setTailorJustification] = useState("");
  const [catalogReqs, setCatalogReqs] = useState<Requirement[]>([]);

  const loadDetail = useCallback(async (id: number) => {
    const { data } = await api.get<ProfileDetail>(`/profiles/${id}`);
    setDetail(data);
    const { data: r } = await api.get<ResolvedProfile>(`/profiles/${id}/resolved`);
    setResolved(r);
  }, []);

  useEffect(() => {
    if (selectedId) void loadDetail(selectedId);
    else {
      setDetail(null);
      setResolved(null);
    }
  }, [selectedId, loadDetail]);

  async function generate() {
    if (!systemId || !genBaseline) return;
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post<ProfileDetail>(`/systems/${systemId}/profiles`, {
        baseline_id: Number(genBaseline),
        name: genName || null,
      });
      setGenOpen(false);
      setGenName("");
      setGenBaseline(null);
      reloadList();
      setSelectedId(data.id);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function openAddControl() {
    if (!detail?.baseline_id) return;
    setTailorAction("add");
    setTailorRequirement(null);
    setTailorJustification("");
    try {
      const { data: baseline } = await api.get<{ catalog_id: number }>(
        `/baselines/${detail.baseline_id}`,
      );
      const { data } = await api.get<Requirement[]>(
        `/frameworks/${baseline.catalog_id}/requirements`,
      );
      const includedIds = new Set(
        detail.controls.filter((c) => c.included).map((c) => c.requirement.id),
      );
      setCatalogReqs(data.filter((r) => !includedIds.has(r.id)));
    } catch (err) {
      setError(errorText(err));
    }
  }

  function openRemove(requirementId: number) {
    setTailorAction("remove");
    setTailorRequirement(requirementId);
    setTailorJustification("");
  }

  async function submitTailoring() {
    if (!detail || !tailorAction || !tailorRequirement || !tailorJustification.trim()) return;
    setError("");
    setBusy(true);
    try {
      await api.post(`/profiles/${detail.id}/tailoring`, {
        action: tailorAction,
        requirement_id: tailorRequirement,
        justification: tailorJustification,
      });
      setTailorAction(null);
      await loadDetail(detail.id);
      reloadList();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    if (!detail) return;
    setBusy(true);
    setError("");
    try {
      await api.post(`/profiles/${detail.id}/approve`);
      await loadDetail(detail.id);
      reloadList();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function newVersion() {
    if (!detail) return;
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<ProfileDetail>(`/profiles/${detail.id}/new-version`);
      reloadList();
      setSelectedId(data.id);
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
          Цільові профілі
        </Title>
        <Alert color="blue" variant="light">
          Оберіть конкретну ІКС у перемикачі вгорі — профілі формуються для системи.
        </Alert>
      </>
    );
  }

  const isDraft = detail?.status === "draft";
  const systemProfiles = systemId ? (profiles as Profile[] | null) : null;

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Цільові профілі</Title>
        <Button onClick={() => setGenOpen(true)}>Згенерувати профіль</Button>
      </Group>
      {error && (
        <Alert color="red" mb="md" onClose={() => setError("")} withCloseButton>
          {error}
        </Alert>
      )}

      <Group align="flex-start" gap="lg" wrap="nowrap">
        <Stack w={320} style={{ flexShrink: 0 }}>
          {!systemProfiles ? (
            <Loader />
          ) : systemProfiles.length === 0 ? (
            <Text c="dimmed">Профілів ще немає. Згенеруйте з baseline.</Text>
          ) : (
            systemProfiles.map((p) => (
              <Card
                key={p.id}
                withBorder
                padding="sm"
                style={{
                  cursor: "pointer",
                  borderColor: p.id === selectedId ? "var(--mantine-color-blue-5)" : undefined,
                }}
                onClick={() => setSelectedId(p.id)}
              >
                <Group justify="space-between">
                  <Text fw={500} size="sm">
                    {p.name}
                  </Text>
                  <Badge size="xs" color={STATUS_COLORS[p.status]} variant="light">
                    {STATUS_LABELS[p.status]}
                  </Badge>
                </Group>
                <Text size="xs" c="dimmed" mt={4}>
                  Версія {p.version} · {p.control_count} контролів
                </Text>
              </Card>
            ))
          )}
        </Stack>

        <Stack style={{ flexGrow: 1, minWidth: 0 }}>
          {!detail ? (
            <Text c="dimmed">Оберіть профіль зліва.</Text>
          ) : (
            <>
              <Group justify="space-between">
                <div>
                  <Title order={3}>
                    {detail.name}{" "}
                    <Badge color={STATUS_COLORS[detail.status]}>
                      {STATUS_LABELS[detail.status]}
                    </Badge>
                  </Title>
                  <Text size="sm" c="dimmed">
                    Версія {detail.version} · {detail.control_count} включених контролів
                  </Text>
                </div>
                <Group gap="xs">
                  {isDraft && (
                    <>
                      <Button size="xs" variant="default" onClick={() => void openAddControl()}>
                        Додати контроль
                      </Button>
                      <Button size="xs" color="green" onClick={() => void approve()} loading={busy}>
                        Затвердити
                      </Button>
                    </>
                  )}
                  {detail.status !== "superseded" && !isDraft && (
                    <Button size="xs" onClick={() => void newVersion()} loading={busy}>
                      Нова версія
                    </Button>
                  )}
                </Group>
              </Group>

              <Tabs defaultValue="controls">
                <Tabs.List>
                  <Tabs.Tab value="controls">Контролі</Tabs.Tab>
                  <Tabs.Tab value="resolved">Резолвлене</Tabs.Tab>
                  <Tabs.Tab value="decisions">
                    Рішення tailoring ({detail.decisions.length})
                  </Tabs.Tab>
                </Tabs.List>

                <Tabs.Panel value="controls" pt="sm">
                  <Table striped>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th w={120}>Код</Table.Th>
                        <Table.Th>Назва</Table.Th>
                        <Table.Th w={110}>Походження</Table.Th>
                        <Table.Th w={120}>Стан</Table.Th>
                        <Table.Th w={120}></Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {detail.controls.map((c) => (
                        <Table.Tr key={c.id} opacity={c.included ? 1 : 0.5}>
                          <Table.Td>{c.requirement.code}</Table.Td>
                          <Table.Td>{c.requirement.title}</Table.Td>
                          <Table.Td>
                            <Badge
                              size="xs"
                              variant="light"
                              color={c.origin === "added" ? "grape" : "blue"}
                            >
                              {c.origin === "added" ? "додано" : "baseline"}
                            </Badge>
                          </Table.Td>
                          <Table.Td>
                            {c.included ? (
                              <Badge size="xs" color="green" variant="light">
                                включено
                              </Badge>
                            ) : (
                              <Badge size="xs" color="red" variant="light">
                                вилучено
                              </Badge>
                            )}
                          </Table.Td>
                          <Table.Td>
                            {isDraft && c.included && (
                              <Button
                                size="compact-xs"
                                color="red"
                                variant="subtle"
                                onClick={() => openRemove(c.requirement.id)}
                              >
                                Вилучити
                              </Button>
                            )}
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Tabs.Panel>

                <Tabs.Panel value="resolved" pt="sm">
                  <Text size="sm" c="dimmed" mb="xs">
                    Підсумковий набір включених контролів із резолвленими значеннями
                    ODP-параметрів (значення профілю або типове).
                  </Text>
                  {resolved?.controls.map((c) => (
                    <Card key={c.requirement_id} withBorder padding="sm" mb="xs">
                      <Text fw={500} size="sm">
                        {c.code} — {c.title}
                      </Text>
                      {c.parameters.length > 0 && (
                        <Stack gap={2} mt={4}>
                          {c.parameters.map((p) => (
                            <Text key={p.parameter_id} size="xs" c="dimmed">
                              {p.label ?? p.key}: <strong>{p.value ?? "—"}</strong>
                            </Text>
                          ))}
                        </Stack>
                      )}
                    </Card>
                  ))}
                </Tabs.Panel>

                <Tabs.Panel value="decisions" pt="sm">
                  {detail.decisions.length === 0 ? (
                    <Text c="dimmed">Рішень tailoring ще немає.</Text>
                  ) : (
                    <Table striped>
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th w={120}>Дія</Table.Th>
                          <Table.Th>Обґрунтування</Table.Th>
                          <Table.Th w={160}>Хто / коли</Table.Th>
                        </Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        {detail.decisions.map((d) => (
                          <Table.Tr key={d.id}>
                            <Table.Td>
                              <Badge size="xs" variant="light">
                                {d.action}
                              </Badge>
                            </Table.Td>
                            <Table.Td>{d.justification}</Table.Td>
                            <Table.Td>
                              <Text size="xs" c="dimmed">
                                {d.created_by?.full_name ?? "—"}
                              </Text>
                            </Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  )}
                </Tabs.Panel>
              </Tabs>
            </>
          )}
        </Stack>
      </Group>

      <Modal opened={genOpen} onClose={() => setGenOpen(false)} title="Згенерувати цільовий профіль">
        <Stack>
          <Select
            label="Базовий набір (baseline)"
            data={
              baselines?.map((b) => ({
                value: String(b.id),
                label: `${b.name} (${b.item_count})`,
              })) ?? []
            }
            value={genBaseline}
            onChange={setGenBaseline}
            required
          />
          <TextInput
            label="Назва профілю"
            description="Необов'язково — за замовчуванням «код ІКС — назва baseline»"
            value={genName}
            onChange={(e) => setGenName(e.currentTarget.value)}
          />
          <Button onClick={() => void generate()} disabled={!genBaseline} loading={busy}>
            Згенерувати
          </Button>
        </Stack>
      </Modal>

      <Modal
        opened={tailorAction !== null}
        onClose={() => setTailorAction(null)}
        title={tailorAction === "add" ? "Додати контроль" : "Вилучити контроль"}
      >
        <Stack>
          {tailorAction === "add" && (
            <Select
              label="Контроль каталогу"
              data={catalogReqs.map((r) => ({
                value: String(r.id),
                label: `${r.code} — ${r.title}`,
              }))}
              value={tailorRequirement ? String(tailorRequirement) : null}
              onChange={(v) => setTailorRequirement(v ? Number(v) : null)}
              searchable
              required
            />
          )}
          <Textarea
            label="Обґрунтування"
            description="Обов'язкове — фіксується в журналі рішень tailoring"
            value={tailorJustification}
            onChange={(e) => setTailorJustification(e.currentTarget.value)}
            minRows={3}
            required
          />
          <Button
            onClick={() => void submitTailoring()}
            loading={busy}
            disabled={!tailorRequirement || !tailorJustification.trim()}
          >
            Зберегти рішення
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
