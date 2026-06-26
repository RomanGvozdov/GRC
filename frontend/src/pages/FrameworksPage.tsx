import {
  Alert,
  Badge,
  Button,
  Card,
  FileButton,
  Group,
  Loader,
  Modal,
  MultiSelect,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useState } from "react";
import {
  api,
  errorText,
  type AiControlSuggestions,
  type Framework,
  type Requirement,
} from "../api";
import { useFetch } from "../components/shared";
import { PROFILE_LABELS, PROFILE_SHORT } from "../labels";

async function downloadFile(url: string, filename: string) {
  const { data } = await api.get(url, { responseType: "blob" });
  const href = URL.createObjectURL(data as Blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(href);
}

export default function FrameworksPage() {
  const { data: frameworks, reload } = useFetch<Framework[]>("/frameworks");
  const [selected, setSelected] = useState<Framework | null>(null);
  const { data: requirements, reload: reloadReqs } = useFetch<Requirement[]>(
    selected ? `/frameworks/${selected.id}/requirements` : "/frameworks",
    [selected?.id],
  );

  const [createOpen, setCreateOpen] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [reqCode, setReqCode] = useState("");
  const [reqTitle, setReqTitle] = useState("");
  const [reqProfiles, setReqProfiles] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  // AI-зіставлення контролів (сценарій 3)
  const [mapTarget, setMapTarget] = useState<string | null>(null);
  const [mapResult, setMapResult] = useState<(AiControlSuggestions & { source: string }) | null>(null);
  const [mapping, setMapping] = useState(false);

  async function mapControl(req: Requirement) {
    if (!mapTarget) return;
    setMapping(true);
    setError("");
    try {
      const { data } = await api.post<AiControlSuggestions>("/ai/map-control", {
        requirement_id: req.id,
        target_framework_id: Number(mapTarget),
      });
      setMapResult({ ...data, source: `${req.code} ${req.title}` });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setMapping(false);
    }
  }

  function toggle(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function call(fn: () => Promise<unknown>, after?: () => void) {
    setError("");
    setBusy(true);
    try {
      await fn();
      after?.();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const createFramework = () =>
    call(
      () => api.post("/frameworks", { code, name }),
      () => {
        setCreateOpen(false);
        setCode("");
        setName("");
        reload();
      },
    );

  const importJson = (file: File | null) => {
    if (!file) return;
    void file.text().then((text) =>
      call(
        () => api.post("/frameworks/import", JSON.parse(text)),
        () => reload(),
      ),
    );
  };

  const addRequirement = () =>
    call(
      () =>
        api.post(`/frameworks/${selected!.id}/requirements`, {
          code: reqCode,
          title: reqTitle,
          profiles: reqProfiles,
        }),
      () => {
        setReqCode("");
        setReqTitle("");
        setReqProfiles([]);
        reloadReqs();
      },
    );

  const deleteRequirement = (requirementId: number) =>
    call(
      () => api.delete(`/frameworks/${selected!.id}/requirements/${requirementId}`),
      () => reloadReqs(),
    );

  const deleteFramework = (framework: Framework) => {
    if (!window.confirm(`Видалити каталог «${framework.name}» з усіма вимогами?`)) return;
    void call(
      () => api.delete(`/frameworks/${framework.id}`),
      () => {
        setSelected(null);
        reload();
      },
    );
  };

  const list = selected && requirements && "length" in requirements ? requirements : null;

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Каталоги вимог</Title>
        <Group>
          <FileButton onChange={importJson} accept="application/json">
            {(props) => (
              <Button variant="default" {...props}>
                Імпорт з JSON
              </Button>
            )}
          </FileButton>
          <Button onClick={() => setCreateOpen(true)}>Новий каталог</Button>
        </Group>
      </Group>
      {error && (
        <Alert color="red" mb="md" onClose={() => setError("")} withCloseButton>
          {error}
        </Alert>
      )}
      <Text size="sm" c="dimmed" mb="md">
        Формат JSON для імпорту: {"{"}"code", "name", "version", "requirements": [{"{"}"code",
        "title", "description", "profiles": ["confidential" | "service"]{"}"}]{"}"} — наприклад,
        повний NIST 800-53 або НД ТЗІ 3.6-006-24 з розподілом за базовими профілями.
      </Text>

      {!frameworks ? (
        <Loader />
      ) : (
        <Group align="start" grow>
          <Card withBorder padding="md">
            <Title order={4} mb="sm">
              Каталоги
            </Title>
            <Table highlightOnHover>
              <Table.Tbody>
                {frameworks.map((framework) => (
                  <Table.Tr
                    key={framework.id}
                    onClick={() => setSelected(framework)}
                    style={{ cursor: "pointer" }}
                    bg={selected?.id === framework.id ? "var(--mantine-color-blue-0)" : undefined}
                  >
                    <Table.Td>
                      {framework.name}
                      {framework.version ? ` (${framework.version})` : ""}
                    </Table.Td>
                    <Table.Td w={120}>
                      {framework.is_custom ? (
                        <Badge variant="light">Кастомний</Badge>
                      ) : (
                        <Badge variant="light" color="gray">
                          Вбудований
                        </Badge>
                      )}
                    </Table.Td>
                    <Table.Td w={120}>
                      <Group gap={4} wrap="nowrap">
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          onClick={(e) => {
                            e.stopPropagation();
                            void downloadFile(
                              `/frameworks/${framework.id}/oscal`,
                              `catalog-${framework.id}-oscal.json`,
                            );
                          }}
                        >
                          OSCAL
                        </Button>
                        {framework.is_custom && (
                          <Button
                            size="compact-xs"
                            color="red"
                            variant="subtle"
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteFramework(framework);
                            }}
                          >
                            ✕
                          </Button>
                        )}
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>

          <Card withBorder padding="md">
            <Group justify="space-between" mb="sm" align="end">
              <Title order={4}>
                {selected ? `Вимоги: ${selected.name}` : "Оберіть каталог"}
              </Title>
              {selected && (
                <Select
                  label="AI-зіставлення з каталогом"
                  placeholder="оберіть цільовий"
                  data={
                    frameworks
                      ?.filter((f) => f.id !== selected.id)
                      .map((f) => ({ value: String(f.id), label: f.name })) ?? []
                  }
                  value={mapTarget}
                  onChange={setMapTarget}
                  clearable
                  w={260}
                  size="xs"
                />
              )}
            </Group>
            {selected?.is_custom && (
              <Group mb="sm" align="end">
                <TextInput
                  label="Код"
                  value={reqCode}
                  onChange={(e) => setReqCode(e.currentTarget.value)}
                  w={120}
                />
                <TextInput
                  label="Назва вимоги"
                  value={reqTitle}
                  onChange={(e) => setReqTitle(e.currentTarget.value)}
                  style={{ flex: 1 }}
                />
                <MultiSelect
                  label="Профілі"
                  data={Object.entries(PROFILE_LABELS).map(([value, label]) => ({ value, label }))}
                  value={reqProfiles}
                  onChange={setReqProfiles}
                  w={200}
                  clearable
                />
                <Button
                  onClick={() => void addRequirement()}
                  disabled={!reqCode || !reqTitle}
                  loading={busy}
                >
                  Додати
                </Button>
              </Group>
            )}
            {selected && (
              <Table striped>
                <Table.Tbody>
                  {list?.map((req) => {
                    const isOpen = expanded.has(req.id);
                    const colSpan = selected.is_custom ? 3 : 2;
                    return (
                      <>
                        <Table.Tr
                          key={req.id}
                          style={{ cursor: req.description ? "pointer" : "default" }}
                          onClick={() => req.description && toggle(req.id)}
                        >
                          <Table.Td w={100}>
                            {req.description ? (isOpen ? "▾ " : "▸ ") : ""}
                            {req.code}
                          </Table.Td>
                          <Table.Td>
                            {req.title}
                            {req.profiles.map((p) => (
                              <Badge key={p} size="xs" ml={6} variant="outline" color="violet">
                                {PROFILE_SHORT[p] ?? p}
                              </Badge>
                            ))}
                            {mapTarget && (
                              <Button
                                size="compact-xs"
                                variant="subtle"
                                ml={6}
                                loading={mapping}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  void mapControl(req);
                                }}
                              >
                                ↔ AI
                              </Button>
                            )}
                          </Table.Td>
                          {selected.is_custom && (
                            <Table.Td w={50}>
                              <Button
                                size="compact-xs"
                                color="red"
                                variant="subtle"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  void deleteRequirement(req.id);
                                }}
                              >
                                ✕
                              </Button>
                            </Table.Td>
                          )}
                        </Table.Tr>
                        {isOpen && req.description && (
                          <Table.Tr key={`${req.id}-desc`}>
                            <Table.Td colSpan={colSpan}>
                              <Text
                                size="sm"
                                c="dimmed"
                                style={{ whiteSpace: "pre-wrap" }}
                                pl="md"
                              >
                                {req.description}
                              </Text>
                            </Table.Td>
                          </Table.Tr>
                        )}
                      </>
                    );
                  })}
                </Table.Tbody>
              </Table>
            )}
          </Card>
        </Group>
      )}

      <Modal opened={createOpen} onClose={() => setCreateOpen(false)} title="Новий каталог">
        <Stack>
          <TextInput
            label="Код (латиниця, без пробілів)"
            placeholder="nd-tzi"
            value={code}
            onChange={(e) => setCode(e.currentTarget.value)}
          />
          <TextInput
            label="Назва"
            placeholder="НД ТЗІ"
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
          />
          <Button onClick={() => void createFramework()} disabled={!code || !name} loading={busy}>
            Створити
          </Button>
        </Stack>
      </Modal>

      <Modal
        opened={mapResult !== null}
        onClose={() => setMapResult(null)}
        title="AI-зіставлення контролів"
        size="lg"
      >
        {mapResult && (
          <Stack>
            <Text size="sm" c="dimmed">
              Джерело: <strong>{mapResult.source}</strong>
            </Text>
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={120}>Кандидат</Table.Th>
                  <Table.Th>Назва</Table.Th>
                  <Table.Th w={90}>Подібність</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {mapResult.suggestions.map((s) => (
                  <Table.Tr key={s.requirement_id}>
                    <Table.Td>{s.code}</Table.Td>
                    <Table.Td>{s.title}</Table.Td>
                    <Table.Td>{Math.round(s.score * 100)}%</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
              {mapResult.rationale}
            </Text>
          </Stack>
        )}
      </Modal>
    </>
  );
}
