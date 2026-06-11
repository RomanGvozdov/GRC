import { Badge, Code, Loader, Table, Title } from "@mantine/core";
import type { AuditEntry } from "../api";
import { EmptyRow, useFetch } from "../components/shared";
import { formatDateTime } from "../labels";

const ACTION_LABELS: Record<string, string> = {
  create: "Створення",
  update: "Оновлення",
  delete: "Видалення",
  assess: "Оцінка",
  comment: "Коментар",
  login: "Вхід",
  logout_all: "Вихід з усіх пристроїв",
  password_changed: "Зміна пароля",
  totp_enabled: "Увімкнення 2FA",
  account_locked: "Блокування акаунта",
  link_controls: "Прив'язка контролів",
  add_evidence: "Додавання доказу",
  delete_evidence: "Видалення доказу",
};

const ENTITY_LABELS: Record<string, string> = {
  user: "Користувач",
  risk: "Ризик",
  control: "Контроль",
  risk_category: "Категорія ризику",
  treatment_action: "Дія з обробки",
};

export default function AuditLogPage() {
  const { data: entries } = useFetch<AuditEntry[]>("/audit-log?limit=200");

  return (
    <>
      <Title order={2} mb="md">
        Журнал дій
      </Title>
      {!entries ? (
        <Loader />
      ) : (
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Час</Table.Th>
              <Table.Th>Користувач</Table.Th>
              <Table.Th>Дія</Table.Th>
              <Table.Th>Об'єкт</Table.Th>
              <Table.Th>Деталі</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {entries.length === 0 && <EmptyRow colSpan={5} />}
            {entries.map((entry) => (
              <Table.Tr key={entry.id}>
                <Table.Td>{formatDateTime(entry.created_at)}</Table.Td>
                <Table.Td>{entry.user?.full_name ?? "—"}</Table.Td>
                <Table.Td>
                  <Badge variant="outline">
                    {ACTION_LABELS[entry.action] ?? entry.action}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  {ENTITY_LABELS[entry.entity_type] ?? entry.entity_type}
                  {entry.entity_id ? ` #${entry.entity_id}` : ""}
                </Table.Td>
                <Table.Td>
                  {entry.details && <Code>{JSON.stringify(entry.details)}</Code>}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </>
  );
}
