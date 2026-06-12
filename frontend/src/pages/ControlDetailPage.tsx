import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  FileButton,
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
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  api,
  errorText,
  type Control,
  type Framework,
  type Implementation,
  type Requirement,
  type SystemBrief,
  type User,
} from "../api";
import { canEdit, canManage, useAuth } from "../auth";
import { ImplBadge, useFetch } from "../components/shared";
import { CONTROL_TYPE_LABELS, formatDate, IMPL_LABELS, toOptions } from "../labels";

export default function ControlDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: control, reload } = useFetch<Control>(`/controls/${id}`);
  const { data: users } = useFetch<User[]>("/users");
  const { data: frameworks } = useFetch<Framework[]>("/frameworks");
  const { data: systems } = useFetch<SystemBrief[]>("/systems");

  const [allRequirements, setAllRequirements] = useState<
    (Requirement & { framework_name: string })[]
  >([]);
  useEffect(() => {
    if (!frameworks) return;
    Promise.all(
      frameworks.map((framework) =>
        api
          .get<Requirement[]>(`/frameworks/${framework.id}/requirements`)
          .then(({ data }) => data.map((req) => ({ ...req, framework_name: framework.name }))),
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
      });
      setRequirementIds(control.requirements.map((req) => String(req.id)));
    }
  }, [control]);

  const [implModal, setImplModal] = useState(false);
  const [implSystemId, setImplSystemId] = useState<string | null>(null);

  if (!control) return <Loader />;
  const editable = canEdit(user, "controls");

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
        requirement_ids: requirementIds.map(Number),
      }),
    );

  const addImplementation = () =>
    call(async () => {
      await api.post(`/controls/${id}/implementations`, {
        system_id: implSystemId ? Number(implSystemId) : null,
      });
      setImplModal(false);
      setImplSystemId(null);
    });

  const patchImpl = (impl: Implementation, changes: Partial<Record<string, unknown>>) =>
    call(() =>
      api.patch(`/controls/${id}/implementations/${impl.id}`, {
        system_id: impl.system?.id ?? null,
        implementation_status: impl.implementation_status,
        na_justification: impl.na_justification,
        review_period_months: impl.review_period_months,
        next_review_date: impl.next_review_date,
        ...changes,
      }),
    );

  const deleteImpl = (impl: Implementation) => {
    if (!window.confirm("Видалити впровадження разом з доказами?")) return;
    void call(() => api.delete(`/controls/${id}/implementations/${impl.id}`));
  };

  const remove = async () => {
    if (!window.confirm(`Видалити контроль ${control.code}?`)) return;
    await api.delete(`/controls/${id}`);
    navigate("/controls");
  };

  const set = (key: string) => (value: string | null) =>
    setForm((f) => ({ ...f, [key]: value }));

  const usedSystemIds = new Set(control.implementations.map((i) => i.system?.id ?? 0));
  const availableSystems = [
    ...(usedSystemIds.has(0) ? [] : [{ value: "", label: "Вся організація" }]),
    ...(systems
      ?.filter((s) => !usedSystemIds.has(s.id))
      .map((s) => ({ value: String(s.id), label: s.name })) ?? []),
  ];

  return (
    <>
      <Group justify="space-between" mb="md">
        <Group>
          <Title order={2}>
            {control.code} — {control.name}
          </Title>
          <ImplBadge status={control.aggregate_status} />
        </Group>
        {canManage(user, "controls") && (
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
        <Grid.Col span={{ base: 12, md: 5 }}>
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
                  label="Відповідальний"
                  data={users?.map((u) => ({ value: String(u.id), label: u.full_name })) ?? []}
                  value={form.owner_id}
                  onChange={set("owner_id")}
                  clearable
                  searchable
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

        <Grid.Col span={{ base: 12, md: 7 }}>
          <Group justify="space-between" mb="sm">
            <Title order={4}>Впровадження по системах</Title>
            {editable && (
              <Button size="xs" onClick={() => setImplModal(true)}>
                Додати впровадження
              </Button>
            )}
          </Group>
          <Stack gap="sm">
            {control.implementations.map((impl) => (
              <ImplementationCard
                key={impl.id}
                controlId={Number(id)}
                impl={impl}
                editable={editable}
                busy={busy}
                onPatch={(changes) => void patchImpl(impl, changes)}
                onDelete={() => deleteImpl(impl)}
                onChanged={reload}
              />
            ))}
          </Stack>
        </Grid.Col>
      </Grid>

      <Modal opened={implModal} onClose={() => setImplModal(false)} title="Нове впровадження">
        <Stack>
          <Select
            label="Система (ІКС)"
            description="Порожнє значення = вся організація"
            data={availableSystems}
            value={implSystemId}
            onChange={setImplSystemId}
            clearable
          />
          <Button onClick={() => void addImplementation()} loading={busy}>
            Додати
          </Button>
        </Stack>
      </Modal>
    </>
  );
}

function ImplementationCard({
  controlId,
  impl,
  editable,
  busy,
  onPatch,
  onDelete,
  onChanged,
}: {
  controlId: number;
  impl: Implementation;
  editable: boolean;
  busy: boolean;
  onPatch: (changes: Record<string, unknown>) => void;
  onDelete: () => void;
  onChanged: () => void;
}) {
  const [naText, setNaText] = useState(impl.na_justification ?? "");
  const [linkName, setLinkName] = useState("");
  const [linkUrl, setLinkUrl] = useState("");

  const addLink = async () => {
    await api.post(`/controls/${controlId}/implementations/${impl.id}/evidence/link`, {
      name: linkName,
      url: linkUrl,
    });
    setLinkName("");
    setLinkUrl("");
    onChanged();
  };

  const uploadFile = async (file: File | null) => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    await api.post(`/controls/${controlId}/implementations/${impl.id}/evidence/file`, form);
    onChanged();
  };

  const downloadEvidence = (evidenceId: number, name: string) => {
    api
      .get(`/controls/${controlId}/evidence/${evidenceId}/download`, { responseType: "blob" })
      .then(({ data }) => {
        const url = URL.createObjectURL(data);
        const a = document.createElement("a");
        a.href = url;
        a.download = name;
        a.click();
        URL.revokeObjectURL(url);
      });
  };

  const deleteEvidence = async (evidenceId: number) => {
    await api.delete(`/controls/${controlId}/evidence/${evidenceId}`);
    onChanged();
  };

  return (
    <Card withBorder padding="sm">
      <Group justify="space-between" mb="xs">
        <Badge variant={impl.system ? "filled" : "outline"} color="indigo">
          {impl.system ? impl.system.name : "Вся організація"}
        </Badge>
        <Group gap="xs">
          {editable ? (
            <Select
              size="xs"
              data={toOptions(IMPL_LABELS)}
              value={impl.implementation_status}
              onChange={(value) => value && onPatch({ implementation_status: value })}
              w={170}
            />
          ) : (
            <ImplBadge status={impl.implementation_status} />
          )}
          {editable && (
            <Button size="compact-xs" color="red" variant="subtle" onClick={onDelete}>
              ✕
            </Button>
          )}
        </Group>
      </Group>

      {impl.implementation_status === "not_applicable" && (
        <Group align="end" mb="xs">
          <Textarea
            label="Обґрунтування незастосовності (для SoA)"
            value={naText}
            onChange={(e) => setNaText(e.currentTarget.value)}
            disabled={!editable}
            style={{ flex: 1 }}
            autosize
            minRows={1}
          />
          {editable && (
            <Button
              size="xs"
              variant="default"
              loading={busy}
              onClick={() => onPatch({ na_justification: naText })}
            >
              Зберегти
            </Button>
          )}
        </Group>
      )}

      <Group align="end" mb="xs">
        <TextInput
          label="Наступна перевірка"
          type="date"
          size="xs"
          defaultValue={impl.next_review_date ?? ""}
          onBlur={(e) => {
            if (editable && e.currentTarget.value !== (impl.next_review_date ?? ""))
              onPatch({ next_review_date: e.currentTarget.value || null });
          }}
          disabled={!editable}
        />
        <Text size="xs" c="dimmed">
          Доказів: {impl.evidence.length}
        </Text>
      </Group>

      {impl.evidence.length > 0 && (
        <Table mb="xs">
          <Table.Tbody>
            {impl.evidence.map((item) => (
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
                  <Text size="xs" c="dimmed" span ml="xs">
                    {formatDate(item.created_at)}
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
      )}

      {editable && (
        <Group gap="xs" align="end">
          <TextInput
            placeholder="Назва посилання"
            size="xs"
            value={linkName}
            onChange={(e) => setLinkName(e.currentTarget.value)}
          />
          <TextInput
            placeholder="URL"
            size="xs"
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.currentTarget.value)}
            style={{ flex: 1 }}
          />
          <Button size="xs" variant="default" disabled={!linkName || !linkUrl} onClick={() => void addLink()}>
            + Посилання
          </Button>
          <FileButton onChange={(f) => void uploadFile(f)}>
            {(props) => (
              <Button size="xs" variant="default" {...props}>
                + Файл
              </Button>
            )}
          </FileButton>
        </Group>
      )}
    </Card>
  );
}
