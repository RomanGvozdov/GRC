import {
  Alert,
  Badge,
  Button,
  Checkbox,
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
  type POAMFromProfile,
  type POAMItem,
  type POAMItemDetail,
  type Profile,
  type User,
} from "../api";
import { useFetch } from "../components/shared";
import { useSystem } from "../systemContext";

const STATUS_LABELS: Record<string, string> = {
  open: "Відкрито",
  in_progress: "В роботі",
  completed: "Виконано",
  risk_accepted: "Ризик прийнято",
};
const STATUS_COLORS: Record<string, string> = {
  open: "red",
  in_progress: "yellow",
  completed: "green",
  risk_accepted: "gray",
};
const SEVERITY_LABELS: Record<string, string> = {
  low: "Низька",
  medium: "Середня",
  high: "Висока",
  critical: "Критична",
};
const SEVERITY_COLORS: Record<string, string> = {
  low: "blue",
  medium: "yellow",
  high: "orange",
  critical: "red",
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

export default function PoamPage() {
  const { systemId } = useSystem();
  const listUrl = systemId ? `/systems/${systemId}/poam` : "/baselines";
  const { data: items, reload } = useFetch<POAMItem[]>(listUrl, [systemId]);
  const profilesUrl = systemId ? `/systems/${systemId}/profiles` : "/baselines";
  const { data: profiles } = useFetch<Profile[]>(profilesUrl, [systemId]);
  const { data: users } = useFetch<User[]>("/users");

  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [weakness, setWeakness] = useState("");
  const [severity, setSeverity] = useState<string | null>(null);

  const [genOpen, setGenOpen] = useState(false);
  const [genProfile, setGenProfile] = useState<string | null>(null);

  const [detail, setDetail] = useState<POAMItemDetail | null>(null);
  const [msTitle, setMsTitle] = useState("");

  const loadDetail = useCallback(async (id: number) => {
    const { data } = await api.get<POAMItemDetail>(`/poam/${id}`);
    setDetail(data);
  }, []);

  useEffect(() => {
    setDetail(null);
  }, [systemId]);

  async function createItem() {
    if (!systemId || !title.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api.post(`/systems/${systemId}/poam`, {
        title,
        weakness: weakness || null,
        severity,
      });
      setCreateOpen(false);
      setTitle("");
      setWeakness("");
      setSeverity(null);
      reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function generateFromGaps() {
    if (!systemId || !genProfile) return;
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<POAMFromProfile>(
        `/systems/${systemId}/poam/from-profile/${genProfile}`,
      );
      setGenOpen(false);
      setGenProfile(null);
      setInfo(`Створено пунктів: ${data.created}, пропущено (вже є): ${data.skipped}`);
      reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(item: POAMItem, statusValue: string) {
    setError("");
    try {
      await api.patch(`/poam/${item.id}`, { status: statusValue });
      reload();
      if (detail?.id === item.id) await loadDetail(item.id);
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function addMilestone() {
    if (!detail || !msTitle.trim()) return;
    setBusy(true);
    try {
      await api.post(`/poam/${detail.id}/milestones`, { title: msTitle });
      setMsTitle("");
      await loadDetail(detail.id);
      reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function toggleMilestone(milestoneId: number, completed: boolean) {
    if (!detail) return;
    await api.patch(`/poam/milestones/${milestoneId}`, { completed });
    await loadDetail(detail.id);
    reload();
  }

  async function setResponsible(value: string | null) {
    if (!detail) return;
    await api.patch(`/poam/${detail.id}`, { responsible_id: value ? Number(value) : null });
    await loadDetail(detail.id);
  }

  if (!systemId) {
    return (
      <>
        <Title order={2} mb="md">
          POA&M — план усунення недоліків
        </Title>
        <Alert color="blue" variant="light">
          Оберіть конкретну ІКС у перемикачі вгорі — POA&M ведеться для системи.
        </Alert>
      </>
    );
  }

  const list = systemId ? (items as POAMItem[] | null) : null;

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>POA&M — план усунення недоліків</Title>
        <Group gap="xs">
          <Button variant="default" onClick={() => setGenOpen(true)}>
            З прогалин профілю
          </Button>
          <Button variant="default" onClick={() => void download(`/systems/${systemId}/poam/oscal`, `poam-${systemId}-oscal.json`)}>
            OSCAL
          </Button>
          <Button variant="default" onClick={() => void download(`/systems/${systemId}/poam/export?fmt=xlsx`, `poam-${systemId}.xlsx`)}>
            XLSX
          </Button>
          <Button onClick={() => setCreateOpen(true)}>Новий пункт</Button>
        </Group>
      </Group>
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

      {!list ? (
        <Loader />
      ) : list.length === 0 ? (
        <Text c="dimmed">Пунктів POA&M немає. Додайте вручну або згенеруйте з прогалин профілю.</Text>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={100}>Контроль</Table.Th>
              <Table.Th>Недолік</Table.Th>
              <Table.Th w={110}>Критичність</Table.Th>
              <Table.Th w={150}>Статус</Table.Th>
              <Table.Th w={110}>Точки</Table.Th>
              <Table.Th w={90}></Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {list.map((it) => (
              <Table.Tr key={it.id}>
                <Table.Td>{it.requirement?.code ?? "—"}</Table.Td>
                <Table.Td>{it.title}</Table.Td>
                <Table.Td>
                  {it.severity ? (
                    <Badge color={SEVERITY_COLORS[it.severity]} variant="light">
                      {SEVERITY_LABELS[it.severity]}
                    </Badge>
                  ) : (
                    "—"
                  )}
                </Table.Td>
                <Table.Td>
                  <Select
                    size="xs"
                    data={Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }))}
                    value={it.status}
                    onChange={(v) => v && void setStatus(it, v)}
                    w={140}
                  />
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" color={it.milestone_done === it.milestone_count && it.milestone_count > 0 ? "green" : "gray"}>
                    {it.milestone_done}/{it.milestone_count}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Button size="compact-xs" variant="subtle" onClick={() => void loadDetail(it.id)}>
                    Деталі
                  </Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={createOpen} onClose={() => setCreateOpen(false)} title="Новий пункт POA&M">
        <Stack>
          <TextInput
            label="Назва недоліку"
            value={title}
            onChange={(e) => setTitle(e.currentTarget.value)}
            required
          />
          <Textarea
            label="Опис"
            value={weakness}
            onChange={(e) => setWeakness(e.currentTarget.value)}
          />
          <Select
            label="Критичність"
            data={Object.entries(SEVERITY_LABELS).map(([value, label]) => ({ value, label }))}
            value={severity}
            onChange={setSeverity}
            clearable
          />
          <Button onClick={() => void createItem()} disabled={!title.trim()} loading={busy}>
            Створити
          </Button>
        </Stack>
      </Modal>

      <Modal opened={genOpen} onClose={() => setGenOpen(false)} title="POA&M із прогалин профілю">
        <Stack>
          <Text size="sm" c="dimmed">
            Створить пункти для контролів профілю, що не покриті або покриті частково.
            Дублі (вже відкриті пункти) пропускаються.
          </Text>
          <Select
            label="Профіль"
            data={profiles?.map((p) => ({ value: String(p.id), label: `${p.name} (v${p.version})` })) ?? []}
            value={genProfile}
            onChange={setGenProfile}
            required
          />
          <Button onClick={() => void generateFromGaps()} disabled={!genProfile} loading={busy}>
            Згенерувати
          </Button>
        </Stack>
      </Modal>

      <Modal
        opened={detail !== null}
        onClose={() => setDetail(null)}
        title={detail?.title ?? ""}
        size="lg"
      >
        {detail && (
          <Stack>
            <Group>
              <Badge color={STATUS_COLORS[detail.status]}>{STATUS_LABELS[detail.status]}</Badge>
              {detail.requirement && <Badge variant="light">{detail.requirement.code}</Badge>}
              <Badge variant="light" color="gray">{detail.source}</Badge>
            </Group>
            {detail.weakness && <Text size="sm">{detail.weakness}</Text>}
            <Select
              label="Відповідальний"
              data={users?.map((u) => ({ value: String(u.id), label: u.full_name })) ?? []}
              value={detail.responsible ? String(detail.responsible.id) : null}
              onChange={(v) => void setResponsible(v)}
              clearable
              searchable
            />
            <Title order={5}>Контрольні точки</Title>
            <Stack gap="xs">
              {detail.milestones.map((m) => (
                <Checkbox
                  key={m.id}
                  label={m.title}
                  checked={m.completed}
                  onChange={(e) => void toggleMilestone(m.id, e.currentTarget.checked)}
                />
              ))}
              {detail.milestones.length === 0 && <Text c="dimmed" size="sm">Точок немає.</Text>}
            </Stack>
            <Group>
              <TextInput
                placeholder="Нова контрольна точка"
                value={msTitle}
                onChange={(e) => setMsTitle(e.currentTarget.value)}
                style={{ flexGrow: 1 }}
              />
              <Button onClick={() => void addMilestone()} disabled={!msTitle.trim()} loading={busy}>
                Додати
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </>
  );
}
