import {
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  Menu,
  Modal,
  Select,
  Stack,
  Table,
  TextInput,
  Title,
} from "@mantine/core";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText, type ControlListItem, type Framework } from "../api";
import ImportModal from "../components/ImportModal";
import { useSystem, withSystem } from "../systemContext";
import { canManage, useAuth } from "../auth";
import { EmptyRow, ImplBadge, useFetch } from "../components/shared";
import { formatDate, IMPL_LABELS, toOptions } from "../labels";

export default function ControlsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [frameworkFilter, setFrameworkFilter] = useState<string | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (statusFilter) params.set("status", statusFilter);
    if (frameworkFilter) params.set("framework_id", frameworkFilter);
    return params.toString();
  }, [search, statusFilter, frameworkFilter]);

  const { systemId } = useSystem();
  const { data: controls, reload } = useFetch<ControlListItem[]>(
    withSystem(`/controls?${query}`, systemId), [systemId],
  );
  const [importOpen, setImportOpen] = useState(false);
  const { data: frameworks } = useFetch<Framework[]>("/frameworks");

  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function createControl() {
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post("/controls", { name, requirement_ids: [] });
      setCreateOpen(false);
      navigate(`/controls/${data.id}`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  function download(fmt: "xlsx" | "csv") {
    api.get(`/exports/controls?fmt=${fmt}`, { responseType: "blob" }).then(({ data }) => {
      const url = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `controls.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Реєстр контролів</Title>
        <Group>
          <Menu>
            <Menu.Target>
              <Button variant="default">Експорт</Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item onClick={() => download("xlsx")}>Excel (.xlsx)</Menu.Item>
              <Menu.Item onClick={() => download("csv")}>CSV</Menu.Item>
            </Menu.Dropdown>
          </Menu>
          {canManage(user, "controls") && (
            <>
              <Button variant="default" onClick={() => setImportOpen(true)}>
                Імпорт
              </Button>
              <Button onClick={() => setCreateOpen(true)}>Новий контроль</Button>
            </>
          )}
        </Group>
      </Group>

      <Group mb="md">
        <TextInput
          placeholder="Пошук за назвою або кодом"
          value={search}
          onChange={(e) => setSearch(e.currentTarget.value)}
          w={260}
        />
        <Select
          placeholder="Статус впровадження"
          data={toOptions(IMPL_LABELS)}
          value={statusFilter}
          onChange={setStatusFilter}
          clearable
        />
        <Select
          placeholder="Фреймворк"
          data={frameworks?.map((f) => ({ value: String(f.id), label: f.name })) ?? []}
          value={frameworkFilter}
          onChange={setFrameworkFilter}
          clearable
        />
      </Group>

      {!controls ? (
        <Loader />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Код</Table.Th>
              <Table.Th>Назва</Table.Th>
              <Table.Th>Статус</Table.Th>
              <Table.Th>Системи</Table.Th>
              <Table.Th>Відповідальний</Table.Th>
              <Table.Th>Вимоги</Table.Th>
              <Table.Th>Наступна перевірка</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {controls.length === 0 && <EmptyRow colSpan={7} />}
            {controls.map((control) => (
              <Table.Tr key={control.id}>
                <Table.Td>
                  <Anchor component={Link} to={`/controls/${control.id}`}>
                    {control.code}
                  </Anchor>
                </Table.Td>
                <Table.Td>{control.name}</Table.Td>
                <Table.Td>
                  <ImplBadge status={control.aggregate_status} />
                </Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    {control.systems.map((s) => (
                      <Badge key={s.id} variant="outline" size="sm" color="indigo">
                        {s.name}
                      </Badge>
                    ))}
                  </Group>
                </Table.Td>
                <Table.Td>{control.owner?.full_name ?? "—"}</Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    {control.requirements.slice(0, 4).map((req) => (
                      <Badge key={req.id} variant="outline" size="sm">
                        {req.code}
                      </Badge>
                    ))}
                    {control.requirements.length > 4 && (
                      <Badge variant="outline" size="sm">
                        +{control.requirements.length - 4}
                      </Badge>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>{formatDate(control.next_review_date)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <ImportModal
        opened={importOpen}
        onClose={() => setImportOpen(false)}
        kind="controls"
        onImported={reload}
      />
      <Modal opened={createOpen} onClose={() => setCreateOpen(false)} title="Новий контроль">
        <Stack>
          {error && <Badge color="red">{error}</Badge>}
          <TextInput
            label="Назва"
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
            required
          />
          <Button onClick={() => void createControl()} loading={busy} disabled={!name}>
            Створити
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
