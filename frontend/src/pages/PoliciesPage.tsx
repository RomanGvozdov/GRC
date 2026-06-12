import {
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  TextInput,
  Title,
} from "@mantine/core";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText, type PolicyListItem } from "../api";
import { canManage, useAuth } from "../auth";
import { EmptyRow, useFetch } from "../components/shared";
import { formatDate, POLICY_STATUS_COLORS, POLICY_STATUS_LABELS } from "../labels";

export default function PoliciesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: policies } = useFetch<PolicyListItem[]>("/policies");

  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [nextReview, setNextReview] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const myPending = policies?.filter((p) => p.pending_my_approval || p.pending_my_ack) ?? [];

  async function createPolicy() {
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post("/policies", {
        title,
        next_review_date: nextReview || null,
      });
      navigate(`/policies/${data.id}`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Політики та документи</Title>
        {canManage(user, "policies") && <Button onClick={() => setCreateOpen(true)}>Нова політика</Button>}
      </Group>

      {myPending.length > 0 && (
        <Stack gap={4} mb="md">
          {myPending.map((policy) => (
            <Group key={policy.id} gap="xs">
              <Badge color={policy.pending_my_approval ? "yellow" : "blue"}>
                {policy.pending_my_approval ? "Очікує вашого погодження" : "Потребує ознайомлення"}
              </Badge>
              <Anchor component={Link} to={`/policies/${policy.id}`} size="sm">
                {policy.code} — {policy.title}
              </Anchor>
            </Group>
          ))}
        </Stack>
      )}

      {!policies ? (
        <Loader />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Код</Table.Th>
              <Table.Th>Назва</Table.Th>
              <Table.Th>Статус</Table.Th>
              <Table.Th>Версія</Table.Th>
              <Table.Th>Відповідальний</Table.Th>
              <Table.Th>Наступний перегляд</Table.Th>
              <Table.Th>Ознайомлення</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {policies.length === 0 && <EmptyRow colSpan={7} />}
            {policies.map((policy) => (
              <Table.Tr key={policy.id}>
                <Table.Td>
                  <Anchor component={Link} to={`/policies/${policy.id}`}>
                    {policy.code}
                  </Anchor>
                </Table.Td>
                <Table.Td>{policy.title}</Table.Td>
                <Table.Td>
                  <Badge color={POLICY_STATUS_COLORS[policy.status]} variant="light">
                    {POLICY_STATUS_LABELS[policy.status]}
                  </Badge>
                </Table.Td>
                <Table.Td>{policy.version_number ?? "—"}</Table.Td>
                <Table.Td>{policy.owner?.full_name ?? "—"}</Table.Td>
                <Table.Td>{formatDate(policy.next_review_date)}</Table.Td>
                <Table.Td>
                  {policy.ack_total > 0 ? `${policy.ack_done}/${policy.ack_total}` : "—"}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={createOpen} onClose={() => setCreateOpen(false)} title="Нова політика">
        <Stack>
          {error && <Badge color="red">{error}</Badge>}
          <TextInput
            label="Назва"
            value={title}
            onChange={(e) => setTitle(e.currentTarget.value)}
            required
          />
          <TextInput
            label="Дата наступного перегляду"
            type="date"
            value={nextReview}
            onChange={(e) => setNextReview(e.currentTarget.value)}
          />
          <Button onClick={() => void createPolicy()} loading={busy} disabled={!title}>
            Створити
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
