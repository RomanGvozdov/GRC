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
import { api, errorText, type Categorization, type System, type User } from "../api";
import { EmptyRow, useFetch } from "../components/shared";
import { LEVEL_COLORS, LEVEL_LABELS, PROFILE_LABELS } from "../labels";

const STATUS_LABELS: Record<string, string> = {
  operational: "Експлуатується",
  development: "Розробляється",
  decommissioned: "Виведена з експлуатації",
};

const IMPACT_LABELS: Record<string, string> = {
  low: "Низький",
  moderate: "Помірний",
  high: "Високий",
};

const IMPACT_OPTIONS = Object.entries(IMPACT_LABELS).map(([value, label]) => ({ value, label }));

export default function SystemsPage() {
  const { data: systems, reload } = useFetch<System[]>("/systems");
  const { data: users } = useFetch<User[]>("/users");

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<System | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [ownerId, setOwnerId] = useState<string | null>(null);
  const [criticality, setCriticality] = useState<string | null>(null);
  const [profileType, setProfileType] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>("operational");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Категоризація
  const [catSystem, setCatSystem] = useState<System | null>(null);
  const [impactC, setImpactC] = useState<string | null>(null);
  const [impactI, setImpactI] = useState<string | null>(null);
  const [impactA, setImpactA] = useState<string | null>(null);
  const [ndProfile, setNdProfile] = useState<string | null>(null);
  const [catResult, setCatResult] = useState<Categorization | null>(null);

  function openCategorize(system: System) {
    setCatSystem(system);
    setImpactC(system.impact_confidentiality);
    setImpactI(system.impact_integrity);
    setImpactA(system.impact_availability);
    setNdProfile(system.profile_type);
    setCatResult(null);
    setError("");
  }

  async function saveCategorization() {
    if (!catSystem) return;
    setError("");
    setBusy(true);
    try {
      const { data } = await api.put<Categorization>(
        `/systems/${catSystem.id}/categorization`,
        {
          impact_confidentiality: impactC,
          impact_integrity: impactI,
          impact_availability: impactA,
          nd_profile_type: ndProfile,
        },
      );
      setCatResult(data);
      reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  function openCreate() {
    setEditing(null);
    setName("");
    setDescription("");
    setOwnerId(null);
    setCriticality(null);
    setProfileType(null);
    setStatus("operational");
    setModalOpen(true);
  }

  function openEdit(system: System) {
    setEditing(system);
    setName(system.name);
    setDescription(system.description ?? "");
    setOwnerId(system.owner ? String(system.owner.id) : null);
    setCriticality(system.criticality);
    setProfileType(system.profile_type);
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
      profile_type: profileType,
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
              <Table.Th>Базовий профіль</Table.Th>
              <Table.Th>Статус</Table.Th>
              <Table.Th>Відповідальний</Table.Th>
              <Table.Th></Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {systems.length === 0 && <EmptyRow colSpan={7} />}
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
                <Table.Td>
                  {system.profile_type ? (
                    <Badge variant="light" color="violet">
                      {PROFILE_LABELS[system.profile_type]}
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
                      variant="light"
                      onClick={() => openCategorize(system)}
                    >
                      Категоризувати
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
          <Select
            label="Тип базового профілю (НД ТЗІ 3.6-006-24)"
            description="Визначає, які вимоги профільних каталогів застосовні до системи"
            data={Object.entries(PROFILE_LABELS).map(([value, label]) => ({ value, label }))}
            value={profileType}
            onChange={setProfileType}
            clearable
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

      <Modal
        opened={catSystem !== null}
        onClose={() => setCatSystem(null)}
        title={catSystem ? `Категоризація: ${catSystem.name}` : ""}
      >
        <Stack>
          <Alert color="blue" variant="light">
            Вкажіть рівні впливу (конфіденційність / цілісність / доступність) або тип
            базового профілю НД ТЗІ. Система запропонує відповідний базовий набір — він
            не застосовується автоматично.
          </Alert>
          <Group grow>
            <Select
              label="Конфіденційність"
              data={IMPACT_OPTIONS}
              value={impactC}
              onChange={setImpactC}
              clearable
            />
            <Select
              label="Цілісність"
              data={IMPACT_OPTIONS}
              value={impactI}
              onChange={setImpactI}
              clearable
            />
            <Select
              label="Доступність"
              data={IMPACT_OPTIONS}
              value={impactA}
              onChange={setImpactA}
              clearable
            />
          </Group>
          <Select
            label="Тип базового профілю (НД ТЗІ 3.6-006-24)"
            data={Object.entries(PROFILE_LABELS).map(([value, label]) => ({ value, label }))}
            value={ndProfile}
            onChange={setNdProfile}
            clearable
          />
          <Button
            onClick={() => void saveCategorization()}
            loading={busy}
            disabled={!impactC && !impactI && !impactA && !ndProfile}
          >
            Зберегти категоризацію
          </Button>
          {catResult && (
            <Alert color="green" variant="light">
              <Stack gap={4}>
                {catResult.overall_impact && (
                  <span>
                    Зведений рівень впливу:{" "}
                    <strong>{IMPACT_LABELS[catResult.overall_impact]}</strong>
                  </span>
                )}
                {catResult.suggested_baseline_id ? (
                  <span>
                    Запропонований базовий набір:{" "}
                    <strong>{catResult.suggested_baseline_name}</strong>
                  </span>
                ) : (
                  <span>
                    Відповідного базового набору ще немає (NIST 800-53B baselines додаються
                    при імпорті OSCAL).
                  </span>
                )}
              </Stack>
            </Alert>
          )}
        </Stack>
      </Modal>
    </>
  );
}
