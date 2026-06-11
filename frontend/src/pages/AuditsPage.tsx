import {
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  Select,
  Stack,
  Table,
  TextInput,
  Title,
} from "@mantine/core";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText, type AuditBrief, type Framework } from "../api";
import { canManage, useAuth } from "../auth";
import { EmptyRow, useFetch } from "../components/shared";
import {
  AUDIT_STATUS_LABELS,
  AUDIT_TYPE_LABELS,
  formatDate,
  toOptions,
} from "../labels";

export default function AuditsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: audits } = useFetch<AuditBrief[]>("/audits");
  const { data: frameworks } = useFetch<Framework[]>("/frameworks");

  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [auditType, setAuditType] = useState<string | null>("internal");
  const [frameworkId, setFrameworkId] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function createAudit() {
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post("/audits", {
        title,
        audit_type: auditType,
        framework_id: frameworkId ? Number(frameworkId) : null,
        date_from: dateFrom || null,
        date_to: dateTo || null,
      });
      navigate(`/audits/${data.id}`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Аудити</Title>
        {canManage(user) && <Button onClick={() => setCreateOpen(true)}>Новий аудит</Button>}
      </Group>

      {!audits ? (
        <Loader />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Код</Table.Th>
              <Table.Th>Назва</Table.Th>
              <Table.Th>Тип</Table.Th>
              <Table.Th>Фреймворк</Table.Th>
              <Table.Th>Період</Table.Th>
              <Table.Th>Аудитор</Table.Th>
              <Table.Th>Статус</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {audits.length === 0 && <EmptyRow colSpan={7} />}
            {audits.map((audit) => (
              <Table.Tr key={audit.id}>
                <Table.Td>
                  <Anchor component={Link} to={`/audits/${audit.id}`}>
                    {audit.code}
                  </Anchor>
                </Table.Td>
                <Table.Td>{audit.title}</Table.Td>
                <Table.Td>{AUDIT_TYPE_LABELS[audit.audit_type]}</Table.Td>
                <Table.Td>{audit.framework?.name ?? "—"}</Table.Td>
                <Table.Td>
                  {formatDate(audit.date_from)} — {formatDate(audit.date_to)}
                </Table.Td>
                <Table.Td>
                  {audit.auditor?.full_name ?? audit.auditor_external ?? "—"}
                </Table.Td>
                <Table.Td>
                  <Badge variant="outline">{AUDIT_STATUS_LABELS[audit.status]}</Badge>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={createOpen} onClose={() => setCreateOpen(false)} title="Новий аудит">
        <Stack>
          {error && <Badge color="red">{error}</Badge>}
          <TextInput
            label="Назва"
            value={title}
            onChange={(e) => setTitle(e.currentTarget.value)}
            required
          />
          <Select
            label="Тип"
            data={toOptions(AUDIT_TYPE_LABELS)}
            value={auditType}
            onChange={setAuditType}
          />
          <Select
            label="Фреймворк (для чек-листа)"
            data={frameworks?.map((f) => ({ value: String(f.id), label: f.name })) ?? []}
            value={frameworkId}
            onChange={setFrameworkId}
            clearable
          />
          <Group grow>
            <TextInput
              label="Початок"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.currentTarget.value)}
            />
            <TextInput
              label="Кінець"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.currentTarget.value)}
            />
          </Group>
          <Button onClick={() => void createAudit()} loading={busy} disabled={!title}>
            Створити
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
