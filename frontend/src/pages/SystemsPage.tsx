import {
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  Select,
  Stack,
  Table,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { useState } from "react";
import { api, errorText, type System, type User } from "../api";
import { EmptyRow, useFetch } from "../components/shared";
import { LEVEL_COLORS, LEVEL_LABELS } from "../labels";

const STATUS_LABELS: Record<string, string> = {
  operational: "Експлуатується",
  development: "Розробляється",
  decommissioned: "Виведена з експлуатації",
};

export default function SystemsPage() {
  const { data: systems, reload } = useFetch<System[]>("/systems");
  const { data: users } = useFetch<User[]>("/users");

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<System | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [ownerId, setOwnerId] = useState<string | null>(null);
  const [criticality, setCriticality] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>("operational");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function openCreate() {
    setEditing(null);
    setName("");
    setDescription("");
    setOwnerId(null);
    setCriticality(null);
    setStatus("operational");
    setModalOpen(true);
  }

  function openEdit(system: System) {
    setEditing(system);
    setName(system.name);
    setDescription(system.description ?? "");
    setOwnerId(system.owner ? String(system.owner.id) : null);
    setCriticality(system.criticality);
    setStatus(system.status);
    setModalOpen(true);
  }

  async function save() {
    setError("");
    setBusy(true);
    const body = {
      name,
      description: description || null,
      owner_id: ownerId ? Number(ownerId) : null,
      criticality,
      status,
    };
    try {
      if (editing) await api.put(`/systems/${editing.id}`, body);
      else await api.post("/systems", body);
      setModalOpen(false);
      reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(system: System) {
    if (!window.confirm(`Видалити систему «${system.name}»?`)) return;
    setError("");
    try {
      await api.delete(`/systems/${system.id}`);
      reload();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Системи (ІКС)</Title>
        <Button onClick={openCreate}>Нова система</Button>
      </Group>
      {error && (
        <Alert color="red" mb="md" onClose={() => setError("")} withCloseButton>
          {error}
        </Alert>
      )}

      {!systems ? (
        <Loader />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Код</Table.Th>
              <Table.Th>Назва</Table.Th>
              <Table.Th>Критичність</Table.Th>
              <Table.Th>Статус</Table.Th>
              <Table.Th>Відповідальний</Table.Th>
              <Table.Th></Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {systems.length === 0 && <EmptyRow colSpan={6} />}
            {systems.map((system) => (
              <Table.Tr key={system.id}>
                <Table.Td>{system.code}</Table.Td>
                <Table.Td>{system.name}</Table.Td>
                <Table.Td>
                  {system.criticality ? (
                    <Badge color={LEVEL_COLORS[system.criticality]} variant="light">
                      {LEVEL_LABELS[system.criticality]}
                    </Badge>
                  ) : (
                    "—"
                  )}
                </Table.Td>
                <Table.Td>{STATUS_LABELS[system.status]}</Table.Td>
                <Table.Td>{system.owner?.full_name ?? "—"}</Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    <Button size="compact-xs" variant="default" onClick={() => openEdit(system)}>
                      Редагувати
                    </Button>
                    <Button
                      size="compact-xs"
                      color="red"
                      variant="subtle"
                      onClick={() => void remove(system)}
                    >
                      Видалити
                    </Button>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal
        opened={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? `Редагувати ${editing.code}` : "Нова система (ІКС)"}
      >
        <Stack>
          <TextInput
            label="Назва"
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
            required
          />
          <Textarea
            label="Опис"
            value={description}
            onChange={(e) => setDescription(e.currentTarget.value)}
          />
          <Select
            label="Відповідальний"
            data={users?.map((u) => ({ value: String(u.id), label: u.full_name })) ?? []}
            value={ownerId}
            onChange={setOwnerId}
            clearable
            searchable
          />
          <Group grow>
            <Select
              label="Критичність"
              data={Object.entries(LEVEL_LABELS).map(([value, label]) => ({ value, label }))}
              value={criticality}
              onChange={setCriticality}
              clearable
            />
            <Select
              label="Статус"
              data={Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }))}
              value={status}
              onChange={setStatus}
            />
          </Group>
          <Button onClick={() => void save()} disabled={!name} loading={busy}>
            Зберегти
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
