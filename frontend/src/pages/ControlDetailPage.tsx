import {
  Alert,
  Anchor,
  Button,
  Card,
  FileButton,
  Grid,
  Group,
  Loader,
  MultiSelect,
  NumberInput,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  api,
  errorText,
  type Control,
  type Framework,
  type Requirement,
  type User,
} from "../api";
import { canEdit, canManage, useAuth } from "../auth";
import { useFetch } from "../components/shared";
import { CONTROL_TYPE_LABELS, formatDate, IMPL_LABELS, toOptions } from "../labels";

export default function ControlDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: control, reload } = useFetch<Control>(`/controls/${id}`);
  const { data: users } = useFetch<User[]>("/users");
  const { data: frameworks } = useFetch<Framework[]>("/frameworks");

  const [allRequirements, setAllRequirements] = useState<
    (Requirement & { framework_name: string })[]
  >([]);
  useEffect(() => {
    if (!frameworks) return;
    Promise.all(
      frameworks.map((framework) =>
        api
          .get<Requirement[]>(`/frameworks/${framework.id}/requirements`)
          .then(({ data }) =>
            data.map((req) => ({ ...req, framework_name: framework.name })),
          ),
      ),
    ).then((lists) => setAllRequirements(lists.flat()));
  }, [frameworks]);

  const requirementOptions = useMemo(
    () =>
      allRequirements.map((req) => ({
        value: String(req.id),
        label: `${req.code} ${req.title} (${req.framework_name})`,
      })),
    [allRequirements],
  );

  const [form, setForm] = useState<Record<string, string | null>>({});
  const [reviewMonths, setReviewMonths] = useState<number | string>("");
  const [requirementIds, setRequirementIds] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (control) {
      setForm({
        name: control.name,
        description: control.description ?? "",
        control_type: control.control_type,
        owner_id: control.owner ? String(control.owner.id) : null,
        implementation_status: control.implementation_status,
        na_justification: control.na_justification ?? "",
        next_review_date: control.next_review_date ?? "",
      });
      setReviewMonths(control.review_period_months ?? "");
      setRequirementIds(control.requirements.map((req) => String(req.id)));
    }
  }, [control]);

  const [linkName, setLinkName] = useState("");
  const [linkUrl, setLinkUrl] = useState("");

  if (!control) return <Loader />;
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

  const save = () =>
    call(() =>
      api.put(`/controls/${id}`, {
        name: form.name,
        description: form.description || null,
        control_type: form.control_type || null,
        owner_id: form.owner_id ? Number(form.owner_id) : null,
        implementation_status: form.implementation_status,
        na_justification: form.na_justification || null,
        review_period_months: reviewMonths === "" ? null : Number(reviewMonths),
        next_review_date: form.next_review_date || null,
        requirement_ids: requirementIds.map(Number),
      }),
    );

  const addLink = () =>
    call(async () => {
      await api.post(`/controls/${id}/evidence/link`, { name: linkName, url: linkUrl });
      setLinkName("");
      setLinkUrl("");
    });

  const uploadFile = (file: File | null) => {
    if (!file) return;
    const data = new FormData();
    data.append("file", file);
    void call(() => api.post(`/controls/${id}/evidence/file`, data));
  };

  const deleteEvidence = (evidenceId: number) =>
    call(() => api.delete(`/controls/${id}/evidence/${evidenceId}`));

  const downloadEvidence = (evidenceId: number, name: string) => {
    api
      .get(`/controls/${id}/evidence/${evidenceId}/download`, { responseType: "blob" })
      .then(({ data }) => {
        const url = URL.createObjectURL(data);
        const a = document.createElement("a");
        a.href = url;
        a.download = name;
        a.click();
        URL.revokeObjectURL(url);
      });
  };

  const remove = async () => {
    if (!window.confirm(`Видалити контроль ${control.code}?`)) return;
    await api.delete(`/controls/${id}`);
    navigate("/controls");
  };

  const set = (key: string) => (value: string | null) =>
    setForm((f) => ({ ...f, [key]: value }));

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>
          {control.code} — {control.name}
        </Title>
        {canManage(user) && (
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
          <Card withBorder padding="md">
            <Title order={4} mb="sm">
              Картка контролю
            </Title>
            <Stack gap="xs">
              <TextInput
                label="Назва"
                value={form.name ?? ""}
                onChange={(e) => set("name")(e.currentTarget.value)}
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
                  label="Тип"
                  data={toOptions(CONTROL_TYPE_LABELS)}
                  value={form.control_type}
                  onChange={set("control_type")}
                  clearable
                  disabled={!editable}
                />
                <Select
                  label="Статус впровадження"
                  data={toOptions(IMPL_LABELS)}
                  value={form.implementation_status}
                  onChange={set("implementation_status")}
                  disabled={!editable}
                />
              </Group>
              {form.implementation_status === "not_applicable" && (
                <Textarea
                  label="Обґрунтування незастосовності (для SoA)"
                  value={form.na_justification ?? ""}
                  onChange={(e) => set("na_justification")(e.currentTarget.value)}
                  disabled={!editable}
                  required
                />
              )}
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
                <NumberInput
                  label="Період перевірки (міс.)"
                  value={reviewMonths}
                  onChange={setReviewMonths}
                  min={1}
                  max={60}
                  disabled={!editable}
                />
                <TextInput
                  label="Наступна перевірка"
                  type="date"
                  value={form.next_review_date ?? ""}
                  onChange={(e) => set("next_review_date")(e.currentTarget.value)}
                  disabled={!editable}
                />
              </Group>
              <MultiSelect
                label="Мапінг на вимоги фреймворків"
                data={requirementOptions}
                value={requirementIds}
                onChange={setRequirementIds}
                searchable
                disabled={!editable}
                limit={50}
              />
              {editable && (
                <Button onClick={() => void save()} loading={busy}>
                  Зберегти
                </Button>
              )}
            </Stack>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 5 }}>
          <Card withBorder padding="md">
            <Title order={4} mb="sm">
              Докази впровадження (evidence)
            </Title>
            <Table mb="sm">
              <Table.Tbody>
                {control.evidence.map((item) => (
                  <Table.Tr key={item.id}>
                    <Table.Td>
                      {item.kind === "link" ? (
                        <Anchor href={item.url ?? "#"} target="_blank" size="sm">
                          {item.name}
                        </Anchor>
                      ) : (
                        <Anchor size="sm" onClick={() => downloadEvidence(item.id, item.name)}>
                          {item.name}
                        </Anchor>
                      )}
                      <Text size="xs" c="dimmed">
                        {item.uploaded_by?.full_name ?? ""} · {formatDate(item.created_at)}
                      </Text>
                    </Table.Td>
                    <Table.Td w={40}>
                      {editable && (
                        <Button
                          size="compact-xs"
                          color="red"
                          variant="subtle"
                          onClick={() => void deleteEvidence(item.id)}
                        >
                          ✕
                        </Button>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            {editable && (
              <Stack gap="xs">
                <Group align="end">
                  <TextInput
                    label="Назва посилання"
                    value={linkName}
                    onChange={(e) => setLinkName(e.currentTarget.value)}
                    style={{ flex: 1 }}
                  />
                  <TextInput
                    label="URL"
                    value={linkUrl}
                    onChange={(e) => setLinkUrl(e.currentTarget.value)}
                    style={{ flex: 1 }}
                  />
                  <Button onClick={() => void addLink()} disabled={!linkName || !linkUrl}>
                    Додати
                  </Button>
                </Group>
                <FileButton onChange={uploadFile}>
                  {(props) => (
                    <Button variant="default" {...props}>
                      Завантажити файл
                    </Button>
                  )}
                </FileButton>
              </Stack>
            )}
          </Card>
        </Grid.Col>
      </Grid>
    </>
  );
}
