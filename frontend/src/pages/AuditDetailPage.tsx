import {
  Alert,
  Anchor,
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
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText, type Audit, type Framework, type User } from "../api";
import { canEdit, canManage, useAuth } from "../auth";
import { useFetch } from "../components/shared";
import {
  ACTION_STATUS_LABELS,
  AUDIT_STATUS_LABELS,
  AUDIT_TYPE_LABELS,
  downloadBlob,
  formatDate,
  RESULT_COLORS,
  RESULT_LABELS,
  SEVERITY_COLORS,
  SEVERITY_LABELS,
  toOptions,
} from "../labels";

export default function AuditDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: audit, reload } = useFetch<Audit>(`/audits/${id}`);
  const { data: frameworks } = useFetch<Framework[]>("/frameworks");
  const { data: users } = useFetch<User[]>("/users");

  const [form, setForm] = useState<Record<string, string | null>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (audit) {
      setForm({
        title: audit.title,
        audit_type: audit.audit_type,
        scope: audit.scope ?? "",
        framework_id: audit.framework ? String(audit.framework.id) : null,
        date_from: audit.date_from ?? "",
        date_to: audit.date_to ?? "",
        auditor_id: audit.auditor ? String(audit.auditor.id) : null,
        auditor_external: audit.auditor_external ?? "",
        status: audit.status,
      });
    }
  }, [audit]);

  const [findingModal, setFindingModal] = useState(false);
  const [findingTitle, setFindingTitle] = useState("");
  const [findingSeverity, setFindingSeverity] = useState<string | null>("medium");
  const [findingAction, setFindingAction] = useState("");
  const [findingResponsible, setFindingResponsible] = useState<string | null>(null);
  const [findingDeadline, setFindingDeadline] = useState("");

  if (!audit) return <Loader />;
  const manager = canManage(user);
  const editable = canEdit(user);

  async function call(fn: () => Promise<unknown>) {
    setError("");
    setBusy(true);
    try {
      await fn();
      reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const saveMeta = () =>
    call(() =>
      api.put(`/audits/${id}`, {
        title: form.title,
        audit_type: form.audit_type,
        scope: form.scope || null,
        framework_id: form.framework_id ? Number(form.framework_id) : null,
        date_from: form.date_from || null,
        date_to: form.date_to || null,
        auditor_id: form.auditor_id ? Number(form.auditor_id) : null,
        auditor_external: form.auditor_external || null,
        status: form.status,
      }),
    );

  const generateChecklist = () => call(() => api.post(`/audits/${id}/checklist/generate`));

  const setItem = (itemId: number, result: string | null, comment: string | null) =>
    call(() => api.patch(`/audits/${id}/checklist/${itemId}`, { result, comment }));

  const addFinding = () =>
    call(async () => {
      await api.post(`/audits/${id}/findings`, {
        title: findingTitle,
        severity: findingSeverity,
        action_title: findingAction || null,
        responsible_id: findingResponsible ? Number(findingResponsible) : null,
        deadline: findingDeadline || null,
      });
      setFindingModal(false);
      setFindingTitle("");
      setFindingAction("");
    });

  const setFindingStatus = (findingId: number, status: string) => {
    const finding = audit.findings.find((f) => f.id === findingId)!;
    return call(() =>
      api.put(`/audits/${id}/findings/${findingId}`, {
        title: finding.title,
        description: finding.description,
        severity: finding.severity,
        control_id: finding.control?.id ?? null,
        requirement_id: finding.requirement_id,
        action_title: finding.action_title,
        responsible_id: finding.responsible?.id ?? null,
        deadline: finding.deadline,
        action_status: status,
      }),
    );
  };

  const createRisk = (findingId: number) =>
    call(() => api.post(`/audits/${id}/findings/${findingId}/create-risk`));

  const downloadPdf = () => {
    api
      .get(`/reports/audit/${id}`, { responseType: "blob" })
      .then(({ data }) => downloadBlob(data, `audit_${audit.code}.pdf`));
  };

  const remove = async () => {
    if (!window.confirm(`Видалити аудит ${audit.code}?`)) return;
    await api.delete(`/audits/${id}`);
    navigate("/audits");
  };

  const set = (key: string) => (value: string | null) =>
    setForm((f) => ({ ...f, [key]: value }));

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>
          {audit.code} — {audit.title}
        </Title>
        <Group>
          <Button variant="default" onClick={downloadPdf}>
            Звіт PDF
          </Button>
          {manager && (
            <Button color="red" variant="outline" onClick={() => void remove()}>
              Видалити
            </Button>
          )}
        </Group>
      </Group>
      {error && (
        <Alert color="red" mb="md" onClose={() => setError("")} withCloseButton>
          {error}
        </Alert>
      )}

      <Card withBorder padding="md" mb="md">
        <Title order={4} mb="sm">
          Параметри аудиту
        </Title>
        <Stack gap="xs">
          <Group grow>
            <TextInput
              label="Назва"
              value={form.title ?? ""}
              onChange={(e) => set("title")(e.currentTarget.value)}
              disabled={!manager}
            />
            <Select
              label="Тип"
              data={toOptions(AUDIT_TYPE_LABELS)}
              value={form.audit_type}
              onChange={set("audit_type")}
              disabled={!manager}
            />
            <Select
              label="Статус"
              data={toOptions(AUDIT_STATUS_LABELS)}
              value={form.status}
              onChange={set("status")}
              disabled={!manager}
            />
          </Group>
          <Group grow>
            <Select
              label="Фреймворк"
              data={frameworks?.map((f) => ({ value: String(f.id), label: f.name })) ?? []}
              value={form.framework_id}
              onChange={set("framework_id")}
              clearable
              disabled={!manager}
            />
            <TextInput
              label="Початок"
              type="date"
              value={form.date_from ?? ""}
              onChange={(e) => set("date_from")(e.currentTarget.value)}
              disabled={!manager}
            />
            <TextInput
              label="Кінець"
              type="date"
              value={form.date_to ?? ""}
              onChange={(e) => set("date_to")(e.currentTarget.value)}
              disabled={!manager}
            />
          </Group>
          <Group grow>
            <Select
              label="Аудитор (внутрішній)"
              data={users?.map((u) => ({ value: String(u.id), label: u.full_name })) ?? []}
              value={form.auditor_id}
              onChange={set("auditor_id")}
              clearable
              searchable
              disabled={!manager}
            />
            <TextInput
              label="Зовнішній аудитор"
              value={form.auditor_external ?? ""}
              onChange={(e) => set("auditor_external")(e.currentTarget.value)}
              disabled={!manager}
            />
          </Group>
          <Textarea
            label="Область (scope)"
            value={form.scope ?? ""}
            onChange={(e) => set("scope")(e.currentTarget.value)}
            disabled={!manager}
          />
          {manager && (
            <Button onClick={() => void saveMeta()} loading={busy} w={200}>
              Зберегти
            </Button>
          )}
        </Stack>
      </Card>

      <Card withBorder padding="md" mb="md">
        <Group justify="space-between" mb="sm">
          <Title order={4}>Чек-лист ({audit.checklist.length})</Title>
          {manager && audit.framework && (
            <Button size="xs" variant="default" onClick={() => void generateChecklist()}>
              Згенерувати з фреймворка
            </Button>
          )}
        </Group>
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Пункт</Table.Th>
              <Table.Th w={170}>Результат</Table.Th>
              <Table.Th>Коментар</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {audit.checklist.map((item) => (
              <Table.Tr key={item.id}>
                <Table.Td>{item.text}</Table.Td>
                <Table.Td>
                  {editable ? (
                    <Select
                      size="xs"
                      data={toOptions(RESULT_LABELS)}
                      value={item.result}
                      onChange={(value) => void setItem(item.id, value, item.comment)}
                      clearable
                    />
                  ) : item.result ? (
                    <Badge color={RESULT_COLORS[item.result]} variant="light">
                      {RESULT_LABELS[item.result]}
                    </Badge>
                  ) : (
                    "—"
                  )}
                </Table.Td>
                <Table.Td>
                  {editable ? (
                    <TextInput
                      size="xs"
                      defaultValue={item.comment ?? ""}
                      onBlur={(e) => {
                        if (e.currentTarget.value !== (item.comment ?? ""))
                          void setItem(item.id, item.result, e.currentTarget.value || null);
                      }}
                    />
                  ) : (
                    item.comment ?? ""
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>

      <Card withBorder padding="md">
        <Group justify="space-between" mb="sm">
          <Title order={4}>Знахідки ({audit.findings.length})</Title>
          {manager && (
            <Button size="xs" onClick={() => setFindingModal(true)}>
              Додати знахідку
            </Button>
          )}
        </Group>
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Код</Table.Th>
              <Table.Th>Знахідка</Table.Th>
              <Table.Th>Критичність</Table.Th>
              <Table.Th>Коригувальна дія</Table.Th>
              <Table.Th>Відповідальний</Table.Th>
              <Table.Th>Дедлайн</Table.Th>
              <Table.Th>Статус дії</Table.Th>
              <Table.Th>Ризик</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {audit.findings.map((finding) => (
              <Table.Tr key={finding.id}>
                <Table.Td>{finding.code}</Table.Td>
                <Table.Td>{finding.title}</Table.Td>
                <Table.Td>
                  <Badge color={SEVERITY_COLORS[finding.severity]} variant="filled">
                    {SEVERITY_LABELS[finding.severity]}
                  </Badge>
                </Table.Td>
                <Table.Td>{finding.action_title ?? "—"}</Table.Td>
                <Table.Td>{finding.responsible?.full_name ?? "—"}</Table.Td>
                <Table.Td>{formatDate(finding.deadline)}</Table.Td>
                <Table.Td>
                  {editable ? (
                    <Select
                      size="xs"
                      data={toOptions(ACTION_STATUS_LABELS)}
                      value={finding.action_status}
                      onChange={(value) => value && void setFindingStatus(finding.id, value)}
                      w={130}
                    />
                  ) : (
                    ACTION_STATUS_LABELS[finding.action_status]
                  )}
                </Table.Td>
                <Table.Td>
                  {finding.risk ? (
                    <Anchor component={Link} to={`/risks/${finding.risk.id}`} size="sm">
                      {finding.risk.code}
                    </Anchor>
                  ) : manager ? (
                    <Button
                      size="compact-xs"
                      variant="subtle"
                      onClick={() => void createRisk(finding.id)}
                    >
                      Створити ризик
                    </Button>
                  ) : (
                    "—"
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
            {audit.findings.length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={8}>
                  <Text c="dimmed" ta="center" py="sm">
                    Знахідок немає
                  </Text>
                </Table.Td>
              </Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </Card>

      <Modal opened={findingModal} onClose={() => setFindingModal(false)} title="Нова знахідка">
        <Stack>
          <TextInput
            label="Опис знахідки"
            value={findingTitle}
            onChange={(e) => setFindingTitle(e.currentTarget.value)}
            required
          />
          <Select
            label="Критичність"
            data={toOptions(SEVERITY_LABELS)}
            value={findingSeverity}
            onChange={setFindingSeverity}
          />
          <TextInput
            label="Коригувальна дія"
            value={findingAction}
            onChange={(e) => setFindingAction(e.currentTarget.value)}
          />
          <Select
            label="Відповідальний"
            data={users?.map((u) => ({ value: String(u.id), label: u.full_name })) ?? []}
            value={findingResponsible}
            onChange={setFindingResponsible}
            clearable
            searchable
          />
          <TextInput
            label="Дедлайн"
            type="date"
            value={findingDeadline}
            onChange={(e) => setFindingDeadline(e.currentTarget.value)}
          />
          <Button onClick={() => void addFinding()} disabled={!findingTitle} loading={busy}>
            Додати
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
