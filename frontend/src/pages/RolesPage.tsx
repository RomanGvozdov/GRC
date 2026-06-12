import {
  Alert,
  Button,
  Group,
  Loader,
  Modal,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useState } from "react";
import { api, errorText, type CustomRole } from "../api";
import { useFetch } from "../components/shared";

const MODULE_LABELS: Record<string, string> = {
  risks: "Ризики",
  controls: "Контролі",
  frameworks: "Каталоги вимог",
  audits: "Аудити",
  policies: "Політики",
  reports: "Звіти та експорт",
  audit_log: "Журнал дій",
  admin: "Адміністрування",
};

const LEVEL_OPTIONS = [
  { value: "none", label: "Немає доступу" },
  { value: "read", label: "Перегляд" },
  { value: "write", label: "Редагування призначеного" },
  { value: "manage", label: "Повне керування" },
];

const MODULES = Object.keys(MODULE_LABELS);

export default function RolesPage() {
  const { data: roles, reload } = useFetch<CustomRole[]>("/roles");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CustomRole | null>(null);
  const [name, setName] = useState("");
  const [permissions, setPermissions] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function openCreate() {
    setEditing(null);
    setName("");
    setPermissions(Object.fromEntries(MODULES.map((m) => [m, "none"])));
    setModalOpen(true);
  }

  function openEdit(role: CustomRole) {
    setEditing(role);
    setName(role.name);
    setPermissions(
      Object.fromEntries(MODULES.map((m) => [m, role.permissions[m] ?? "none"])),
    );
    setModalOpen(true);
  }

  async function save() {
    setError("");
    setBusy(true);
    try {
      if (editing) await api.put(`/roles/${editing.id}`, { name, permissions });
      else await api.post("/roles", { name, permissions });
      setModalOpen(false);
      reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(role: CustomRole) {
    if (!window.confirm(`Видалити роль «${role.name}»?`)) return;
    setError("");
    try {
      await api.delete(`/roles/${role.id}`);
      reload();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Кастомні ролі</Title>
        <Button onClick={openCreate}>Нова роль</Button>
      </Group>
      {error && (
        <Alert color="red" mb="md" onClose={() => setError("")} withCloseButton>
          {error}
        </Alert>
      )}
      <Text size="sm" c="dimmed" mb="md">
        Вбудовані ролі (адміністратор, GRC-менеджер, виконавець, читач) мають фіксовані
        дозволи. Кастомна роль, призначена користувачеві, повністю заміщує дозволи його
        вбудованої ролі.
      </Text>

      {!roles ? (
        <Loader />
      ) : (
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Назва</Table.Th>
              <Table.Th>Дозволи</Table.Th>
              <Table.Th w={180}></Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {roles.length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={3}>
                  <Text c="dimmed" ta="center" py="md">
                    Кастомних ролей немає
                  </Text>
                </Table.Td>
              </Table.Tr>
            )}
            {roles.map((role) => (
              <Table.Tr key={role.id}>
                <Table.Td>{role.name}</Table.Td>
                <Table.Td>
                  <Text size="sm">
                    {MODULES.filter((m) => (role.permissions[m] ?? "none") !== "none")
                      .map(
                        (m) =>
                          `${MODULE_LABELS[m]}: ${
                            LEVEL_OPTIONS.find((o) => o.value === role.permissions[m])?.label
                          }`,
                      )
                      .join("; ") || "Без доступу"}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    <Button size="compact-xs" variant="default" onClick={() => openEdit(role)}>
                      Редагувати
                    </Button>
                    <Button
                      size="compact-xs"
                      color="red"
                      variant="subtle"
                      onClick={() => void remove(role)}
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
        title={editing ? "Редагувати роль" : "Нова роль"}
        size="lg"
      >
        <Stack>
          <TextInput
            label="Назва ролі"
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
            required
          />
          <SimpleGrid cols={2}>
            {MODULES.map((module) => (
              <Select
                key={module}
                label={MODULE_LABELS[module]}
                data={LEVEL_OPTIONS}
                value={permissions[module] ?? "none"}
                onChange={(value) =>
                  value && setPermissions((p) => ({ ...p, [module]: value }))
                }
              />
            ))}
          </SimpleGrid>
          <Button onClick={() => void save()} disabled={!name} loading={busy}>
            Зберегти
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
