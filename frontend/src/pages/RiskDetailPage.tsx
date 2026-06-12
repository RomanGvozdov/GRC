import {
  Alert,
  Anchor,
  Button,
  Card,
  Grid,
  Group,
  Loader,
  Modal,
  MultiSelect,
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
import {
  api,
  errorText,
  type Category,
  type Comment,
  type ControlListItem,
  type Risk,
  type SystemBrief,
  type User,
} from "../api";
import { canEdit, canManage, useAuth } from "../auth";
import { LevelBadge, useFetch } from "../components/shared";
import {
  ACTION_STATUS_LABELS,
  formatDate,
  formatDateTime,
  RISK_STATUS_LABELS,
  STRATEGY_LABELS,
  toOptions,
} from "../labels";

const SCALE = ["1", "2", "3", "4", "5"];

export default function RiskDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: risk, reload } = useFetch<Risk>(`/risks/${id}`);
  const { data: categories } = useFetch<Category[]>("/risk-categories");
  const { data: users } = useFetch<User[]>("/users");
  const { data: allControls } = useFetch<ControlListItem[]>("/controls");
  const { data: comments, reload: reloadComments } = useFetch<Comment[]>(`/comments/risk/${id}`);
  const { data: allSystems } = useFetch<SystemBrief[]>("/systems");
  const [systemIds, setSystemIds] = useState<string[]>([]);

  const [form, setForm] = useState<Record<string, string | null>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (risk) {
      setForm({
        title: risk.title,
        description: risk.description ?? "",
        assets: risk.assets ?? "",
        threat_source: risk.threat_source ?? "",
        vulnerability: risk.vulnerability ?? "",
        category_id: risk.category ? String(risk.category.id) : null,
        owner_id: risk.owner ? String(risk.owner.id) : null,
        next_review_date: risk.next_review_date ?? "",
        status: risk.status,
        treatment_strategy: risk.treatment_strategy,
        acceptance_comment: risk.acceptance_comment ?? "",
      });
    }
  }, [risk]);

  const [assessKind, setAssessKind] = useState<string | null>("residual");
  const [likelihood, setLikelihood] = useState<string | null>(null);
  const [impact, setImpact] = useState<string | null>(null);

  const [actionModal, setActionModal] = useState(false);
  const [actionTitle, setActionTitle] = useState("");
  const [actionAssignee, setActionAssignee] = useState<string | null>(null);
  const [actionDeadline, setActionDeadline] = useState("");

  const [controlIds, setControlIds] = useState<string[]>([]);
  useEffect(() => {
    if (risk) {
      setControlIds(risk.controls.map((c) => String(c.id)));
      setSystemIds(risk.systems.map((s) => String(s.id)));
    }
  }, [risk]);

  const [commentText, setCommentText] = useState("");

  if (!risk) return <Loader />;
  const editable = canEdit(user, "risks");

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

  const save = () =>
    call(() =>
      api.put(`/risks/${id}`, {
        title: form.title,
        description: form.description || null,
        assets: form.assets || null,
        threat_source: form.threat_source || null,
        vulnerability: form.vulnerability || null,
        category_id: form.category_id ? Number(form.category_id) : null,
        owner_id: form.owner_id ? Number(form.owner_id) : null,
        next_review_date: form.next_review_date || null,
        status: form.status,
        treatment_strategy: form.treatment_strategy || null,
        acceptance_comment: form.acceptance_comment || null,
        system_ids: systemIds.map(Number),
      }),
    );

  const addAssessment = () =>
    call(() =>
      api.post(`/risks/${id}/assessments`, {
        kind: assessKind,
        likelihood: Number(likelihood),
        impact: Number(impact),
      }),
    );

  const addAction = () =>
    call(async () => {
      await api.post(`/risks/${id}/actions`, {
        title: actionTitle,
        assignee_id: actionAssignee ? Number(actionAssignee) : null,
        deadline: actionDeadline || null,
        status: "open",
      });
      setActionModal(false);
      setActionTitle("");
      setActionAssignee(null);
      setActionDeadline("");
    });

  const setActionStatus = (actionId: number, status: string) => {
    const action = risk.actions.find((a) => a.id === actionId)!;
    return call(() =>
      api.patch(`/risks/${id}/actions/${actionId}`, {
        title: action.title,
        assignee_id: action.assignee?.id ?? null,
        deadline: action.deadline,
        status,
      }),
    );
  };

  const saveControls = () =>
    call(() => api.put(`/risks/${id}/controls`, controlIds.map(Number)));

  const remove = async () => {
    if (!window.confirm(`Видалити ризик ${risk.code}?`)) return;
    await api.delete(`/risks/${id}`);
    navigate("/risks");
  };

  const addComment = async () => {
    await api.post(`/comments/risk/${id}`, { text: commentText });
    setCommentText("");
    reloadComments();
  };

  const set = (key: string) => (value: string | null) =>
    setForm((f) => ({ ...f, [key]: value }));

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>
          {risk.code} — {risk.title}
        </Title>
        {canManage(user, "risks") && (
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

      <Grid>
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Card withBorder padding="md" mb="md">
            <Title order={4} mb="sm">
              Картка ризику
            </Title>
            <Stack gap="xs">
              <TextInput
                label="Назва"
                value={form.title ?? ""}
                onChange={(e) => set("title")(e.currentTarget.value)}
                disabled={!editable}
              />
              <Textarea
                label="Опис"
                value={form.description ?? ""}
                onChange={(e) => set("description")(e.currentTarget.value)}
                disabled={!editable}
              />
              <Group grow>
                <Select
                  label="Категорія"
                  data={categories?.map((c) => ({ value: String(c.id), label: c.name })) ?? []}
                  value={form.category_id}
                  onChange={set("category_id")}
                  clearable
                  disabled={!editable}
                />
                <Select
                  label="Статус"
                  data={toOptions(RISK_STATUS_LABELS)}
                  value={form.status}
                  onChange={set("status")}
                  disabled={!editable}
                />
              </Group>
              <Group grow>
                <Select
                  label="Відповідальний"
                  data={users?.map((u) => ({ value: String(u.id), label: u.full_name })) ?? []}
                  value={form.owner_id}
                  onChange={set("owner_id")}
                  clearable
                  searchable
                  disabled={!editable}
                />
                <TextInput
                  label="Наступний перегляд"
                  type="date"
                  value={form.next_review_date ?? ""}
                  onChange={(e) => set("next_review_date")(e.currentTarget.value)}
                  disabled={!editable}
                />
              </Group>
              <MultiSelect
                label="Системи (ІКС)"
                description="Порожньо = загальноорганізаційний ризик"
                data={allSystems?.map((s) => ({ value: String(s.id), label: s.name })) ?? []}
                value={systemIds}
                onChange={setSystemIds}
                searchable
                disabled={!editable}
              />
              <Textarea
                label="Активи / процеси"
                value={form.assets ?? ""}
                onChange={(e) => set("assets")(e.currentTarget.value)}
                disabled={!editable}
              />
              <Group grow>
                <Textarea
                  label="Джерело загрози"
                  value={form.threat_source ?? ""}
                  onChange={(e) => set("threat_source")(e.currentTarget.value)}
                  disabled={!editable}
                />
                <Textarea
                  label="Вразливість"
                  value={form.vulnerability ?? ""}
                  onChange={(e) => set("vulnerability")(e.currentTarget.value)}
                  disabled={!editable}
                />
              </Group>
              <Group grow>
                <Select
                  label="Стратегія обробки"
                  data={toOptions(STRATEGY_LABELS)}
                  value={form.treatment_strategy}
                  onChange={set("treatment_strategy")}
                  clearable
                  disabled={!editable}
                />
                <Textarea
                  label="Коментар до прийняття ризику"
                  description="Обов'язковий при прийнятті ризику високого рівня"
                  value={form.acceptance_comment ?? ""}
                  onChange={(e) => set("acceptance_comment")(e.currentTarget.value)}
                  disabled={!editable}
                />
              </Group>
              {risk.accepted_by && (
                <Text size="sm" c="dimmed">
                  Прийняття затвердив: {risk.accepted_by.full_name} (
                  {risk.accepted_at ? formatDateTime(risk.accepted_at) : ""})
                </Text>
              )}
              {editable && (
                <Button onClick={() => void save()} loading={busy}>
                  Зберегти
                </Button>
              )}
            </Stack>
          </Card>

          <Card withBorder padding="md" mb="md">
            <Group justify="space-between" mb="sm">
              <Title order={4}>План обробки</Title>
              {editable && <Button size="xs" onClick={() => setActionModal(true)}>Додати дію</Button>}
            </Group>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Дія</Table.Th>
                  <Table.Th>Виконавець</Table.Th>
                  <Table.Th>Дедлайн</Table.Th>
                  <Table.Th>Статус</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {risk.actions.map((action) => (
                  <Table.Tr key={action.id}>
                    <Table.Td>{action.title}</Table.Td>
                    <Table.Td>{action.assignee?.full_name ?? "—"}</Table.Td>
                    <Table.Td>{formatDate(action.deadline)}</Table.Td>
                    <Table.Td>
                      {editable ? (
                        <Select
                          size="xs"
                          data={toOptions(ACTION_STATUS_LABELS)}
                          value={action.status}
                          onChange={(value) =>
                            value && void setActionStatus(action.id, value)
                          }
                          w={140}
                        />
                      ) : (
                        ACTION_STATUS_LABELS[action.status]
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>

          <Card withBorder padding="md">
            <Title order={4} mb="sm">
              Коментарі
            </Title>
            <Stack gap="xs">
              {comments?.map((comment) => (
                <div key={comment.id}>
                  <Text size="sm" fw={600}>
                    {comment.author?.full_name ?? "—"}{" "}
                    <Text span c="dimmed" size="xs">
                      {formatDateTime(comment.created_at)}
                    </Text>
                  </Text>
                  <Text size="sm">{comment.text}</Text>
                </div>
              ))}
              {canEdit(user, "risks") && (
                <Group>
                  <TextInput
                    placeholder="Новий коментар"
                    value={commentText}
                    onChange={(e) => setCommentText(e.currentTarget.value)}
                    style={{ flex: 1 }}
                  />
                  <Button disabled={!commentText} onClick={() => void addComment()}>
                    Додати
                  </Button>
                </Group>
              )}
            </Stack>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 5 }}>
          <Card withBorder padding="md" mb="md">
            <Title order={4} mb="sm">
              Оцінка
            </Title>
            <Group mb="sm">
              <div>
                <Text size="sm" c="dimmed">
                  Притаманний ризик
                </Text>
                <LevelBadge score={risk.inherent_score} />
              </div>
              <div>
                <Text size="sm" c="dimmed">
                  Залишковий ризик
                </Text>
                <LevelBadge score={risk.residual_score} />
              </div>
            </Group>
            {editable && (
              <Group align="end" mb="sm">
                <Select
                  label="Тип"
                  data={[
                    { value: "inherent", label: "Притаманний" },
                    { value: "residual", label: "Залишковий" },
                  ]}
                  value={assessKind}
                  onChange={setAssessKind}
                  w={130}
                />
                <Select label="Ймовірність" data={SCALE} value={likelihood} onChange={setLikelihood} w={110} />
                <Select label="Вплив" data={SCALE} value={impact} onChange={setImpact} w={90} />
                <Button
                  onClick={() => void addAssessment()}
                  disabled={!likelihood || !impact}
                  loading={busy}
                >
                  Оцінити
                </Button>
              </Group>
            )}
            <Title order={6} mb="xs">
              Історія оцінок
            </Title>
            <Table>
              <Table.Tbody>
                {[...risk.assessments].reverse().map((assessment) => (
                  <Table.Tr key={assessment.id}>
                    <Table.Td>
                      {assessment.kind === "inherent" ? "Притаманний" : "Залишковий"}
                    </Table.Td>
                    <Table.Td>
                      Й{assessment.likelihood} × В{assessment.impact} ={" "}
                      {assessment.likelihood * assessment.impact}
                    </Table.Td>
                    <Table.Td>{assessment.assessed_by?.full_name ?? "—"}</Table.Td>
                    <Table.Td>{formatDateTime(assessment.assessed_at)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>

          <Card withBorder padding="md">
            <Title order={4} mb="sm">
              Пов'язані контролі
            </Title>
            {editable && (
              <Group mb="sm" align="end">
                <MultiSelect
                  data={
                    allControls?.map((c) => ({
                      value: String(c.id),
                      label: `${c.code} ${c.name}`,
                    })) ?? []
                  }
                  value={controlIds}
                  onChange={setControlIds}
                  searchable
                  style={{ flex: 1 }}
                />
                <Button onClick={() => void saveControls()} loading={busy}>
                  Зберегти
                </Button>
              </Group>
            )}
            <Stack gap="xs">
              {risk.controls.map((control) => (
                <Group key={control.id} justify="space-between">
                  <Anchor component={Link} to={`/controls/${control.id}`} size="sm">
                    {control.code} — {control.name}
                  </Anchor>
                </Group>
              ))}
            </Stack>
          </Card>
        </Grid.Col>
      </Grid>

      <Modal opened={actionModal} onClose={() => setActionModal(false)} title="Нова дія">
        <Stack>
          <TextInput
            label="Опис дії"
            value={actionTitle}
            onChange={(e) => setActionTitle(e.currentTarget.value)}
            required
          />
          <Select
            label="Виконавець"
            data={users?.map((u) => ({ value: String(u.id), label: u.full_name })) ?? []}
            value={actionAssignee}
            onChange={setActionAssignee}
            clearable
            searchable
          />
          <TextInput
            label="Дедлайн"
            type="date"
            value={actionDeadline}
            onChange={(e) => setActionDeadline(e.currentTarget.value)}
          />
          <Button onClick={() => void addAction()} disabled={!actionTitle} loading={busy}>
            Додати
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
