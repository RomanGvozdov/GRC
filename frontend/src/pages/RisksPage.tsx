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
  Textarea,
  Title,
} from "@mantine/core";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText, type Category, type RiskBrief, type User } from "../api";
import { canManage, useAuth } from "../auth";
import { EmptyRow, LevelBadge, useFetch } from "../components/shared";
import { formatDate, RISK_STATUS_LABELS, toOptions } from "../labels";

export default function RisksPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [levelFilter, setLevelFilter] = useState<string | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (statusFilter) params.set("status", statusFilter);
    if (levelFilter) params.set("level", levelFilter);
    return params.toString();
  }, [search, statusFilter, levelFilter]);

  const { data: risks } = useFetch<RiskBrief[]>(`/risks?${query}`);
  const { data: categories } = useFetch<Category[]>("/risk-categories");
  const { data: users } = useFetch<User[]>("/users");

  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [ownerId, setOwnerId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function createRisk() {
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post("/risks", {
        title,
        description: description || null,
        category_id: categoryId ? Number(categoryId) : null,
        owner_id: ownerId ? Number(ownerId) : null,
        status: "identified",
      });
      setCreateOpen(false);
      navigate(`/risks/${data.id}`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  function download(fmt: "xlsx" | "csv") {
    api
      .get(`/exports/risks?fmt=${fmt}`, { responseType: "blob" })
      .then(({ data }) => {
        const url = URL.createObjectURL(data);
        const a = document.createElement("a");
        a.href = url;
        a.download = `risks.${fmt}`;
        a.click();
        URL.revokeObjectURL(url);
      });
  }

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Реєстр ризиків</Title>
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
          {canManage(user) && (
            <Button onClick={() => setCreateOpen(true)}>Новий ризик</Button>
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
          placeholder="Статус"
          data={toOptions(RISK_STATUS_LABELS)}
          value={statusFilter}
          onChange={setStatusFilter}
          clearable
        />
        <Select
          placeholder="Рівень (залишковий)"
          data={[
            { value: "low", label: "Низький" },
            { value: "medium", label: "Середній" },
            { value: "high", label: "Високий" },
            { value: "critical", label: "Критичний" },
          ]}
          value={levelFilter}
          onChange={setLevelFilter}
          clearable
        />
      </Group>

      {!risks ? (
        <Loader />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Код</Table.Th>
              <Table.Th>Назва</Table.Th>
              <Table.Th>Категорія</Table.Th>
              <Table.Th>Статус</Table.Th>
              <Table.Th>Залишковий рівень</Table.Th>
              <Table.Th>Відповідальний</Table.Th>
              <Table.Th>Наступний перегляд</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {risks.length === 0 && <EmptyRow colSpan={7} />}
            {risks.map((risk) => (
              <Table.Tr key={risk.id}>
                <Table.Td>
                  <Anchor component={Link} to={`/risks/${risk.id}`}>
                    {risk.code}
                  </Anchor>
                </Table.Td>
                <Table.Td>{risk.title}</Table.Td>
                <Table.Td>{risk.category?.name ?? "—"}</Table.Td>
                <Table.Td>
                  <Badge variant="outline">{RISK_STATUS_LABELS[risk.status]}</Badge>
                </Table.Td>
                <Table.Td>
                  <LevelBadge score={risk.residual_score} />
                </Table.Td>
                <Table.Td>{risk.owner?.full_name ?? "—"}</Table.Td>
                <Table.Td>{formatDate(risk.next_review_date)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={createOpen} onClose={() => setCreateOpen(false)} title="Новий ризик">
        <Stack>
          {error && <Badge color="red">{error}</Badge>}
          <TextInput
            label="Назва"
            value={title}
            onChange={(e) => setTitle(e.currentTarget.value)}
            required
          />
          <Textarea
            label="Опис"
            value={description}
            onChange={(e) => setDescription(e.currentTarget.value)}
          />
          <Select
            label="Категорія"
            data={categories?.map((c) => ({ value: String(c.id), label: c.name })) ?? []}
            value={categoryId}
            onChange={setCategoryId}
            clearable
          />
          <Select
            label="Відповідальний"
            data={users?.map((u) => ({ value: String(u.id), label: u.full_name })) ?? []}
            value={ownerId}
            onChange={setOwnerId}
            clearable
            searchable
          />
          <Button onClick={() => void createRisk()} loading={busy} disabled={!title}>
            Створити
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
