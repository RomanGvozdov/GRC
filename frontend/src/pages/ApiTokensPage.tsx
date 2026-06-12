import {
  Alert,
  Button,
  Code,
  Group,
  Loader,
  Modal,
  NumberInput,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useState } from "react";
import { api, errorText, type APIToken, type User } from "../api";
import { useFetch } from "../components/shared";
import { formatDate, formatDateTime } from "../labels";

export default function ApiTokensPage() {
  const { data: tokens, reload } = useFetch<APIToken[]>("/api-tokens");
  const { data: users } = useFetch<User[]>("/users");

  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [userId, setUserId] = useState<string | null>(null);
  const [expiresDays, setExpiresDays] = useState<number | string>(365);
  const [createdToken, setCreatedToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function createToken() {
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post("/api-tokens", {
        name,
        user_id: Number(userId),
        expires_days: expiresDays === "" ? null : Number(expiresDays),
      });
      setCreatedToken(data.token);
      setName("");
      reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(token: APIToken) {
    if (!window.confirm(`Відкликати токен «${token.name}»? Інтеграція втратить доступ.`)) return;
    await api.delete(`/api-tokens/${token.id}`);
    reload();
  }

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>API-токени</Title>
        <Button
          onClick={() => {
            setCreatedToken("");
            setCreateOpen(true);
          }}
        >
          Новий токен
        </Button>
      </Group>
      {error && (
        <Alert color="red" mb="md" onClose={() => setError("")} withCloseButton>
          {error}
        </Alert>
      )}
      <Text size="sm" c="dimmed" mb="md">
        Токени для інтеграцій (сканери, SIEM, HR-системи). Передаються в заголовку{" "}
        <Code>Authorization: Bearer grc_…</Code> і діють від імені обраного користувача з його
        дозволами. Документація API: <Code>/docs</Code>.
      </Text>

      {!tokens ? (
        <Loader />
      ) : (
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Назва</Table.Th>
              <Table.Th>Префікс</Table.Th>
              <Table.Th>Діє від імені</Table.Th>
              <Table.Th>Створений</Table.Th>
              <Table.Th>Діє до</Table.Th>
              <Table.Th>Останнє використання</Table.Th>
              <Table.Th></Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {tokens.length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={7}>
                  <Text c="dimmed" ta="center" py="md">
                    Токенів немає
                  </Text>
                </Table.Td>
              </Table.Tr>
            )}
            {tokens.map((token) => (
              <Table.Tr key={token.id}>
                <Table.Td>{token.name}</Table.Td>
                <Table.Td>
                  <Code>{token.token_prefix}…</Code>
                </Table.Td>
                <Table.Td>{token.user.full_name}</Table.Td>
                <Table.Td>{formatDate(token.created_at)}</Table.Td>
                <Table.Td>{token.expires_at ? formatDate(token.expires_at) : "Безстроковий"}</Table.Td>
                <Table.Td>
                  {token.last_used_at ? formatDateTime(token.last_used_at) : "—"}
                </Table.Td>
                <Table.Td>
                  <Button
                    size="compact-xs"
                    color="red"
                    variant="subtle"
                    onClick={() => void revoke(token)}
                  >
                    Відкликати
                  </Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={createOpen} onClose={() => setCreateOpen(false)} title="Новий API-токен">
        {createdToken ? (
          <Stack>
            <Alert color="yellow" title="Збережіть токен зараз">
              Токен показується лише один раз. Після закриття вікна його неможливо переглянути.
            </Alert>
            <Code block>{createdToken}</Code>
            <Button onClick={() => setCreateOpen(false)}>Готово</Button>
          </Stack>
        ) : (
          <Stack>
            <TextInput
              label="Назва (призначення)"
              placeholder="SIEM-інтеграція"
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
              required
            />
            <Select
              label="Діє від імені користувача"
              description="Токен успадковує роль і дозволи цього користувача"
              data={
                users?.map((u) => ({
                  value: String(u.id),
                  label: `${u.full_name} (${u.email})`,
                })) ?? []
              }
              value={userId}
              onChange={setUserId}
              searchable
            />
            <NumberInput
              label="Термін дії (днів, порожньо = безстроковий)"
              value={expiresDays}
              onChange={setExpiresDays}
              min={1}
              max={3650}
            />
            <Button onClick={() => void createToken()} disabled={!name || !userId} loading={busy}>
              Створити
            </Button>
          </Stack>
        )}
      </Modal>
    </>
  );
}
