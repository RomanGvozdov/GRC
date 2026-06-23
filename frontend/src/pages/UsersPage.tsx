import {
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  PasswordInput,
  Select,
  Stack,
  Switch,
  Table,
  TextInput,
  Title,
} from "@mantine/core";
import { useState } from "react";
import { api, errorText, type CustomRole, type User } from "../api";
import { useFetch } from "../components/shared";
import { formatDate, ROLE_LABELS, toOptions } from "../labels";

export default function UsersPage() {
  const { data: users, reload } = useFetch<User[]>("/users");
  const { data: customRoles } = useFetch<CustomRole[]>("/roles");

  const roleOptions = [
    ...Object.entries(ROLE_LABELS).map(([value, label]) => ({
      value: `builtin:${value}`,
      label,
    })),
    ...(customRoles?.map((r) => ({ value: `custom:${r.id}`, label: `★ ${r.name}` })) ?? []),
  ];

  function roleValue(row: User): string {
    return row.custom_role ? `custom:${row.custom_role.id}` : `builtin:${row.role}`;
  }

  function changeRole(row: User, value: string) {
    const [kind, id] = value.split(":");
    if (kind === "custom") void patch(row.id, { custom_role_id: Number(id) });
    else void patch(row.id, { role: id, clear_custom_role: true });
  }
  const [createOpen, setCreateOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<string | null>("reader");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);

  const [resetUser, setResetUser] = useState<User | null>(null);
  const [resetPassword, setResetPassword] = useState("");

  async function doResetPassword() {
    if (!resetUser || resetPassword.length < 12) return;
    setError("");
    setSuccess("");
    setBusy(true);
    try {
      await api.patch(`/users/${resetUser.id}`, { password: resetPassword });
      setSuccess(
        `Пароль для ${resetUser.email} змінено. Повідомте новий пароль користувачу — ` +
          "усі його поточні сесії завершено.",
      );
      setResetUser(null);
      setResetPassword("");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function createUser() {
    setError("");
    setBusy(true);
    try {
      await api.post("/users", { email, full_name: fullName, password, role });
      setCreateOpen(false);
      setEmail("");
      setFullName("");
      setPassword("");
      reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function patch(userId: number, body: Record<string, unknown>) {
    setError("");
    try {
      await api.patch(`/users/${userId}`, body);
      reload();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Користувачі</Title>
        <Button onClick={() => setCreateOpen(true)}>Новий користувач</Button>
      </Group>
      {error && (
        <Alert color="red" mb="md" onClose={() => setError("")} withCloseButton>
          {error}
        </Alert>
      )}
      {success && (
        <Alert color="green" mb="md" onClose={() => setSuccess("")} withCloseButton>
          {success}
        </Alert>
      )}

      {!users ? (
        <Loader />
      ) : (
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Ім'я</Table.Th>
              <Table.Th>Email</Table.Th>
              <Table.Th>Роль</Table.Th>
              <Table.Th>2FA</Table.Th>
              <Table.Th>Активний</Table.Th>
              <Table.Th>Створений</Table.Th>
              <Table.Th></Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {users.map((row) => (
              <Table.Tr key={row.id}>
                <Table.Td>{row.full_name}</Table.Td>
                <Table.Td>{row.email}</Table.Td>
                <Table.Td>
                  <Select
                    size="xs"
                    data={roleOptions}
                    value={roleValue(row)}
                    onChange={(value) => value && changeRole(row, value)}
                    w={180}
                  />
                </Table.Td>
                <Table.Td>
                  {row.totp_enabled ? (
                    <Badge color="green" variant="light">
                      Увімкнено
                    </Badge>
                  ) : (
                    <Badge color="gray" variant="light">
                      Не налаштовано
                    </Badge>
                  )}
                </Table.Td>
                <Table.Td>
                  <Switch
                    checked={row.is_active}
                    onChange={(e) =>
                      void patch(row.id, { is_active: e.currentTarget.checked })
                    }
                  />
                </Table.Td>
                <Table.Td>{formatDate(row.created_at)}</Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    <Button
                      size="compact-xs"
                      variant="subtle"
                      onClick={() => {
                        setResetUser(row);
                        setResetPassword("");
                      }}
                    >
                      Скинути пароль
                    </Button>
                    {row.totp_enabled && (
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        color="orange"
                        onClick={() => {
                          if (window.confirm(`Скинути 2FA для ${row.email}?`))
                            void patch(row.id, { reset_totp: true });
                        }}
                      >
                        Скинути 2FA
                      </Button>
                    )}
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={createOpen} onClose={() => setCreateOpen(false)} title="Новий користувач">
        <Stack>
          <TextInput
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.currentTarget.value)}
            required
          />
          <TextInput
            label="Повне ім'я"
            value={fullName}
            onChange={(e) => setFullName(e.currentTarget.value)}
            required
          />
          <PasswordInput
            label="Тимчасовий пароль"
            description="Мінімум 12 символів. Користувач налаштує 2FA при першому вході"
            value={password}
            onChange={(e) => setPassword(e.currentTarget.value)}
            required
          />
          <Select label="Роль" data={toOptions(ROLE_LABELS)} value={role} onChange={setRole} />
          <Button
            onClick={() => void createUser()}
            loading={busy}
            disabled={!email || !fullName || password.length < 12}
          >
            Створити
          </Button>
        </Stack>
      </Modal>

      <Modal
        opened={resetUser !== null}
        onClose={() => setResetUser(null)}
        title={resetUser ? `Скинути пароль: ${resetUser.full_name}` : ""}
      >
        <Stack>
          <PasswordInput
            label="Новий пароль"
            description="Мінімум 12 символів. Усі поточні сесії користувача буде завершено."
            value={resetPassword}
            onChange={(e) => setResetPassword(e.currentTarget.value)}
            required
          />
          <Button
            onClick={() => void doResetPassword()}
            loading={busy}
            disabled={resetPassword.length < 12}
          >
            Скинути пароль
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
