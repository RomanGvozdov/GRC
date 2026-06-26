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
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  errorText,
  type AiDraft,
  type Profile,
  type SSP,
  type SSPControl,
  type SSPDetail,
  type User,
} from "../api";
import { ImplBadge, useFetch } from "../components/shared";
import { IMPL_LABELS } from "../labels";
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

async function download(url: string, filename: string) {
  const { data } = await api.get(url, { responseType: "blob" });
  const href = URL.createObjectURL(data as Blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(href);
}

export default function SSPPage() {
  const { systemId } = useSystem();
  const listUrl = systemId ? `/systems/${systemId}/ssp` : "/baselines";
  const { data: ssps, reload } = useFetch<SSP[]>(listUrl, [systemId]);
  const profilesUrl = systemId ? `/systems/${systemId}/profiles` : "/baselines";
  const { data: profiles } = useFetch<Profile[]>(profilesUrl, [systemId]);
  const { data: users } = useFetch<User[]>("/users");

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<SSPDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [genOpen, setGenOpen] = useState(false);
  const [genProfile, setGenProfile] = useState<string | null>(null);
  const [genTitle, setGenTitle] = useState("");

  const [editControl, setEditControl] = useState<SSPControl | null>(null);
  const [editStatus, setEditStatus] = useState<string | null>(null);
  const [editNarrative, setEditNarrative] = useState("");
  const [editResponsible, setEditResponsible] = useState<string | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [aiNote, setAiNote] = useState("");

  const loadDetail = useCallback(async (id: number) => {
    const { data } = await api.get<SSPDetail>(`/ssp/${id}`);
    setDetail(data);
  }, []);

  useEffect(() => {
    if (selectedId) void loadDetail(selectedId);
    else setDetail(null);
  }, [selectedId, loadDetail]);

  async function generate() {
    if (!systemId || !genProfile) return;
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post<SSPDetail>(`/systems/${systemId}/ssp`, {
        profile_id: Number(genProfile),
        title: genTitle || null,
      });
      setGenOpen(false);
      setGenTitle("");
      setGenProfile(null);
      reload();
      setSelectedId(data.id);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  function openEdit(c: SSPControl) {
    setEditControl(c);
    setEditStatus(c.implementation_status);
    setEditNarrative(c.narrative ?? "");
    setEditResponsible(c.responsible ? String(c.responsible.id) : null);
    setAiNote("");
  }

  async function aiDraft() {
    if (!editControl || !systemId) return;
    setDrafting(true);
    setError("");
    setAiNote("");
    try {
      const { data } = await api.post<AiDraft>("/ai/draft-narrative", {
        kind: "ssp_control",
        requirement_id: editControl.requirement.id,
        system_id: systemId,
      });
      setEditNarrative(data.draft);
      setAiNote("Чернетку згенеровано AI — перевірте й відредагуйте перед збереженням.");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setDrafting(false);
    }
  }

  async function saveControl() {
    if (!detail || !editControl) return;
    setBusy(true);
    setError("");
    try {
      await api.put(`/ssp/${detail.id}/controls/${editControl.requirement.id}`, {
        implementation_status: editStatus,
        narrative: editNarrative || null,
        responsible_id: editResponsible ? Number(editResponsible) : null,
      });
      setEditControl(null);
      await loadDetail(detail.id);
      reload();
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
      await api.post(`/ssp/${detail.id}/approve`);
      await loadDetail(detail.id);
      reload();
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
      const { data } = await api.post<SSPDetail>(`/ssp/${detail.id}/new-version`);
      reload();
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
          SSP — план безпеки
        </Title>
        <Alert color="blue" variant="light">
          Оберіть конкретну ІКС у перемикачі вгорі — SSP формується для системи.
        </Alert>
      </>
    );
  }

  const isDraft = detail?.status === "draft";
  const sspList = systemId ? (ssps as SSP[] | null) : null;

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>SSP — план безпеки</Title>
        <Button onClick={() => setGenOpen(true)}>Згенерувати SSP</Button>
      </Group>
      {error && (
        <Alert color="red" mb="md" onClose={() => setError("")} withCloseButton>
          {error}
        </Alert>
      )}

      <Group align="flex-start" gap="lg" wrap="nowrap">
        <Stack w={300} style={{ flexShrink: 0 }}>
          {!sspList ? (
            <Loader />
          ) : sspList.length === 0 ? (
            <Text c="dimmed">SSP ще немає. Згенеруйте з профілю.</Text>
          ) : (
            sspList.map((s) => (
              <Card
                key={s.id}
                withBorder
                padding="sm"
                style={{
                  cursor: "pointer",
                  borderColor: s.id === selectedId ? "var(--mantine-color-blue-5)" : undefined,
                }}
                onClick={() => setSelectedId(s.id)}
              >
                <Group justify="space-between">
                  <Text fw={500} size="sm">
                    {s.title}
                  </Text>
                  <Badge size="xs" color={STATUS_COLORS[s.status]} variant="light">
                    {STATUS_LABELS[s.status]}
                  </Badge>
                </Group>
                <Text size="xs" c="dimmed" mt={4}>
                  Версія {s.version} · впроваджено {s.implemented_count}/{s.control_count}
                </Text>
              </Card>
            ))
          )}
        </Stack>

        <Stack style={{ flexGrow: 1, minWidth: 0 }}>
          {!detail ? (
            <Text c="dimmed">Оберіть SSP зліва.</Text>
          ) : (
            <>
              <Group justify="space-between">
                <div>
                  <Title order={3}>
                    {detail.title}{" "}
                    <Badge color={STATUS_COLORS[detail.status]}>
                      {STATUS_LABELS[detail.status]}
                    </Badge>
                  </Title>
                  <Text size="sm" c="dimmed">
                    Версія {detail.version} · впроваджено {detail.implemented_count}/
                    {detail.control_count}
                  </Text>
                </div>
                <Group gap="xs">
                  <Button
                    size="xs"
                    variant="default"
                    onClick={() => void download(`/ssp/${detail.id}/oscal`, `ssp-${detail.id}-oscal.json`)}
                  >
                    OSCAL
                  </Button>
                  <Button
                    size="xs"
                    variant="default"
                    onClick={() => void download(`/ssp/${detail.id}/export?fmt=xlsx`, `ssp-${detail.id}.xlsx`)}
                  >
                    XLSX
                  </Button>
                  {isDraft && (
                    <Button size="xs" color="green" onClick={() => void approve()} loading={busy}>
                      Затвердити
                    </Button>
                  )}
                  {detail.status !== "superseded" && !isDraft && (
                    <Button size="xs" onClick={() => void newVersion()} loading={busy}>
                      Нова версія
                    </Button>
                  )}
                </Group>
              </Group>

              <Table striped>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th w={110}>Контроль</Table.Th>
                    <Table.Th>Назва</Table.Th>
                    <Table.Th w={130}>Статус</Table.Th>
                    <Table.Th>Опис впровадження</Table.Th>
                    {isDraft && <Table.Th w={100}></Table.Th>}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {detail.controls.map((c) => (
                    <Table.Tr key={c.id}>
                      <Table.Td>{c.requirement.code}</Table.Td>
                      <Table.Td>{c.requirement.title}</Table.Td>
                      <Table.Td>
                        <ImplBadge status={c.implementation_status} />
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" lineClamp={2} c={c.narrative ? undefined : "dimmed"}>
                          {c.narrative || "—"}
                        </Text>
                      </Table.Td>
                      {isDraft && (
                        <Table.Td>
                          <Button size="compact-xs" variant="subtle" onClick={() => openEdit(c)}>
                            Заповнити
                          </Button>
                        </Table.Td>
                      )}
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </>
          )}
        </Stack>
      </Group>

      <Modal opened={genOpen} onClose={() => setGenOpen(false)} title="Згенерувати SSP із профілю">
        <Stack>
          <Select
            label="Цільовий профіль"
            data={
              profiles?.map((p) => ({
                value: String(p.id),
                label: `${p.name} (v${p.version}, ${p.control_count})`,
              })) ?? []
            }
            value={genProfile}
            onChange={setGenProfile}
            required
          />
          <TextInput
            label="Назва SSP"
            description="Необов'язково"
            value={genTitle}
            onChange={(e) => setGenTitle(e.currentTarget.value)}
          />
          <Button onClick={() => void generate()} disabled={!genProfile} loading={busy}>
            Згенерувати
          </Button>
        </Stack>
      </Modal>

      <Modal
        opened={editControl !== null}
        onClose={() => setEditControl(null)}
        title={editControl ? `Контроль ${editControl.requirement.code}` : ""}
        size="lg"
      >
        <Stack>
          <Select
            label="Статус впровадження"
            data={Object.entries(IMPL_LABELS).map(([value, label]) => ({ value, label }))}
            value={editStatus}
            onChange={setEditStatus}
          />
          <Select
            label="Відповідальний"
            data={users?.map((u) => ({ value: String(u.id), label: u.full_name })) ?? []}
            value={editResponsible}
            onChange={setEditResponsible}
            clearable
            searchable
          />
          <Group justify="space-between" align="end">
            <Textarea
              label="Опис впровадження"
              description="Як саме реалізовано контроль у цій ІКС"
              value={editNarrative}
              onChange={(e) => setEditNarrative(e.currentTarget.value)}
              minRows={5}
              autosize
              style={{ flexGrow: 1 }}
            />
          </Group>
          <Button variant="default" size="xs" onClick={() => void aiDraft()} loading={drafting}>
            ✨ AI-чернетка
          </Button>
          {aiNote && (
            <Alert color="blue" variant="light" p="xs">
              {aiNote}
            </Alert>
          )}
          <Button onClick={() => void saveControl()} loading={busy}>
            Зберегти
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
