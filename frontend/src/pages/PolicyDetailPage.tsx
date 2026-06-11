import {
  Alert,
  Badge,
  Button,
  Card,
  Grid,
  Group,
  Loader,
  Modal,
  MultiSelect,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorText, type Policy, type User } from "../api";
import { canManage, useAuth } from "../auth";
import { useFetch } from "../components/shared";
import {
  formatDate,
  formatDateTime,
  POLICY_STATUS_COLORS,
  POLICY_STATUS_LABELS,
} from "../labels";

const DECISION_LABELS: Record<string, string> = {
  pending: "Очікує",
  approved: "Погоджено",
  rejected: "Відхилено",
};
const DECISION_COLORS: Record<string, string> = {
  pending: "gray",
  approved: "green",
  rejected: "red",
};

export default function PolicyDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: policy, reload } = useFetch<Policy>(`/policies/${id}`);
  const { data: users } = useFetch<User[]>("/users");

  const [content, setContent] = useState("");
  const [nextReview, setNextReview] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [submitModal, setSubmitModal] = useState(false);
  const [approverIds, setApproverIds] = useState<string[]>([]);
  const [ackModal, setAckModal] = useState(false);
  const [ackUserIds, setAckUserIds] = useState<string[]>([]);
  const [rejectComment, setRejectComment] = useState("");

  useEffect(() => {
    if (policy) {
      setContent(policy.current_version?.content_md ?? "");
      setNextReview(policy.next_review_date ?? "");
    }
  }, [policy]);

  if (!policy) return <Loader />;
  const manager = canManage(user);
  const version = policy.current_version;
  const editableContent =
    manager && (policy.status === "draft" || policy.status === "review");
  const myApproval = version?.approvals.find(
    (a) => a.approver.id === user?.id && a.decision === "pending",
  );
  const myAck = version?.acks.find((a) => a.user.id === user?.id && !a.acknowledged_at);

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

  const saveContent = () => call(() => api.put(`/policies/${id}/content`, { content_md: content }));
  const saveMeta = () =>
    call(() =>
      api.put(`/policies/${id}`, {
        title: policy.title,
        owner_id: policy.owner?.id ?? null,
        next_review_date: nextReview || null,
        control_ids: policy.controls.map((c) => c.id),
      }),
    );
  const submit = () =>
    call(async () => {
      await api.post(`/policies/${id}/submit`, { approver_ids: approverIds.map(Number) });
      setSubmitModal(false);
    });
  const decide = (decision: "approved" | "rejected") =>
    call(() =>
      api.post(`/policies/${id}/decide`, {
        decision,
        comment: rejectComment || null,
      }),
    );
  const activate = () => call(() => api.post(`/policies/${id}/activate`));
  const newVersion = () => call(() => api.post(`/policies/${id}/new-version`));
  const archive = () => {
    if (window.confirm("Архівувати політику?")) void call(() => api.post(`/policies/${id}/archive`));
  };
  const assignAcks = () =>
    call(async () => {
      await api.post(`/policies/${id}/acks`, { user_ids: ackUserIds.map(Number) });
      setAckModal(false);
      setAckUserIds([]);
    });
  const acknowledge = () => call(() => api.post(`/policies/${id}/acknowledge`));
  const remove = async () => {
    if (!window.confirm(`Видалити чернетку ${policy.code}?`)) return;
    await api.delete(`/policies/${id}`);
    navigate("/policies");
  };

  return (
    <>
      <Group justify="space-between" mb="md">
        <Group>
          <Title order={2}>
            {policy.code} — {policy.title}
          </Title>
          <Badge color={POLICY_STATUS_COLORS[policy.status]} size="lg">
            {POLICY_STATUS_LABELS[policy.status]}
          </Badge>
          {version && <Badge variant="outline">Версія {version.number}</Badge>}
        </Group>
        {manager && policy.status === "draft" && (
          <Button color="red" variant="outline" onClick={() => void remove()}>
            Видалити
          </Button>
        )}
      </Group>
      {error && (
        <Alert color="red" mb="md" onClose={() => setError("")} withCloseButton>
          {error}
        </Alert>
      )}

      {myAck && (
        <Alert color="blue" mb="md" title="Потрібне ознайомлення">
          <Group>
            <Text size="sm">Прочитайте політику та підтвердьте ознайомлення.</Text>
            <Button size="xs" onClick={() => void acknowledge()} loading={busy}>
              Підтверджую ознайомлення
            </Button>
          </Group>
        </Alert>
      )}

      {myApproval && (
        <Alert color="yellow" mb="md" title="Очікується ваше рішення">
          <Stack gap="xs">
            <TextInput
              placeholder="Коментар (обов'язковий при відхиленні)"
              value={rejectComment}
              onChange={(e) => setRejectComment(e.currentTarget.value)}
            />
            <Group>
              <Button size="xs" color="green" onClick={() => void decide("approved")} loading={busy}>
                Погодити
              </Button>
              <Button
                size="xs"
                color="red"
                variant="outline"
                onClick={() => void decide("rejected")}
                disabled={!rejectComment}
                loading={busy}
              >
                Відхилити
              </Button>
            </Group>
          </Stack>
        </Alert>
      )}

      <Grid>
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Card withBorder padding="md" mb="md">
            <Group justify="space-between" mb="sm">
              <Title order={4}>Текст політики (Markdown)</Title>
              {editableContent && (
                <Button size="xs" onClick={() => void saveContent()} loading={busy}>
                  Зберегти текст
                </Button>
              )}
            </Group>
            {editableContent ? (
              <Textarea
                value={content}
                onChange={(e) => setContent(e.currentTarget.value)}
                autosize
                minRows={14}
              />
            ) : (
              <Text style={{ whiteSpace: "pre-wrap" }} size="sm">
                {version?.content_md || "Текст не додано"}
              </Text>
            )}
          </Card>

          {manager && (
            <Card withBorder padding="md">
              <Title order={4} mb="sm">
                Дії
              </Title>
              <Group>
                {(policy.status === "draft" || policy.status === "review") && (
                  <Button onClick={() => setSubmitModal(true)}>Подати на погодження</Button>
                )}
                {policy.status === "approved" && (
                  <Button color="green" onClick={() => void activate()}>
                    Ввести в дію
                  </Button>
                )}
                {policy.status === "active" && (
                  <>
                    <Button variant="default" onClick={() => setAckModal(true)}>
                      Призначити ознайомлення
                    </Button>
                    <Button variant="default" onClick={() => void newVersion()}>
                      Нова версія
                    </Button>
                  </>
                )}
                {policy.status !== "archived" && policy.status !== "draft" && (
                  <Button color="dark" variant="outline" onClick={archive}>
                    Архівувати
                  </Button>
                )}
              </Group>
              <Group mt="md" align="end">
                <TextInput
                  label="Наступний перегляд"
                  type="date"
                  value={nextReview}
                  onChange={(e) => setNextReview(e.currentTarget.value)}
                />
                <Button variant="default" onClick={() => void saveMeta()}>
                  Зберегти
                </Button>
              </Group>
            </Card>
          )}
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 5 }}>
          {version && version.approvals.length > 0 && (
            <Card withBorder padding="md" mb="md">
              <Title order={4} mb="sm">
                Погодження (версія {version.number})
              </Title>
              <Table>
                <Table.Tbody>
                  {version.approvals.map((approval) => (
                    <Table.Tr key={approval.id}>
                      <Table.Td>{approval.approver.full_name}</Table.Td>
                      <Table.Td>
                        <Badge color={DECISION_COLORS[approval.decision]} variant="light">
                          {DECISION_LABELS[approval.decision]}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        {approval.decided_at ? formatDateTime(approval.decided_at) : "—"}
                        {approval.comment && (
                          <Text size="xs" c="dimmed">
                            {approval.comment}
                          </Text>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Card>
          )}

          {version && version.acks.length > 0 && (
            <Card withBorder padding="md" mb="md">
              <Title order={4} mb="sm">
                Ознайомлення ({version.acks.filter((a) => a.acknowledged_at).length}/
                {version.acks.length})
              </Title>
              <Table>
                <Table.Tbody>
                  {version.acks.map((ack) => (
                    <Table.Tr key={ack.id}>
                      <Table.Td>{ack.user.full_name}</Table.Td>
                      <Table.Td>
                        {ack.acknowledged_at ? (
                          <Badge color="green" variant="light">
                            {formatDateTime(ack.acknowledged_at)}
                          </Badge>
                        ) : (
                          <Badge color="gray" variant="light">
                            Очікує
                          </Badge>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Card>
          )}

          <Card withBorder padding="md">
            <Title order={4} mb="sm">
              Історія версій
            </Title>
            <Table>
              <Table.Tbody>
                {[...policy.versions].reverse().map((v) => (
                  <Table.Tr key={v.id}>
                    <Table.Td>Версія {v.number}</Table.Td>
                    <Table.Td>{formatDate(v.created_at)}</Table.Td>
                    <Table.Td>
                      {v.activated_at
                        ? `діє з ${formatDate(v.activated_at)}`
                        : v.approved_at
                          ? "затверджена"
                          : "чернетка"}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>
        </Grid.Col>
      </Grid>

      <Modal opened={submitModal} onClose={() => setSubmitModal(false)} title="Подати на погодження">
        <Stack>
          <MultiSelect
            label="Погоджувачі"
            data={users?.map((u) => ({ value: String(u.id), label: u.full_name })) ?? []}
            value={approverIds}
            onChange={setApproverIds}
            searchable
          />
          <Button onClick={() => void submit()} disabled={approverIds.length === 0} loading={busy}>
            Подати
          </Button>
        </Stack>
      </Modal>

      <Modal opened={ackModal} onClose={() => setAckModal(false)} title="Призначити ознайомлення">
        <Stack>
          <MultiSelect
            label="Користувачі"
            data={users?.map((u) => ({ value: String(u.id), label: u.full_name })) ?? []}
            value={ackUserIds}
            onChange={setAckUserIds}
            searchable
          />
          <Button onClick={() => void assignAcks()} disabled={ackUserIds.length === 0} loading={busy}>
            Призначити
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
