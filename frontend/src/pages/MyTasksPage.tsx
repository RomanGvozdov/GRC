import { Anchor, Badge, Loader, Table, Text, Title } from "@mantine/core";
import { Link } from "react-router-dom";
import type { MyTask } from "../api";
import { EmptyRow, useFetch } from "../components/shared";
import { formatDate } from "../labels";

const KIND_LABELS: Record<string, string> = {
  treatment_action: "Дія з обробки ризику",
  finding: "Коригувальна дія",
  approval: "Погодження політики",
  ack: "Ознайомлення",
  risk_review: "Перегляд ризику",
  control_review: "Перевірка контролю",
  policy_review: "Перегляд політики",
};

const KIND_COLORS: Record<string, string> = {
  treatment_action: "blue",
  finding: "grape",
  approval: "yellow",
  ack: "cyan",
  risk_review: "orange",
  control_review: "orange",
  policy_review: "orange",
};

const ENTITY_PATHS: Record<string, string> = {
  risk: "/risks",
  audit: "/audits",
  policy: "/policies",
  control: "/controls",
};

export default function MyTasksPage() {
  const { data: tasks } = useFetch<MyTask[]>("/my-tasks");

  return (
    <>
      <Title order={2} mb="md">
        Мої задачі
      </Title>
      {!tasks ? (
        <Loader />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Тип</Table.Th>
              <Table.Th>Що зробити</Table.Th>
              <Table.Th>Об'єкт</Table.Th>
              <Table.Th>Термін</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {tasks.length === 0 && (
              <EmptyRow colSpan={4} text="Усе виконано — задач немає 🎉" />
            )}
            {tasks.map((task, index) => (
              <Table.Tr key={index}>
                <Table.Td>
                  <Badge color={KIND_COLORS[task.kind] ?? "gray"} variant="light">
                    {KIND_LABELS[task.kind] ?? task.kind}
                  </Badge>
                </Table.Td>
                <Table.Td>{task.title}</Table.Td>
                <Table.Td>
                  <Anchor
                    component={Link}
                    to={`${ENTITY_PATHS[task.entity_type] ?? "/"}/${task.entity_id}`}
                    size="sm"
                  >
                    {task.entity_code}
                  </Anchor>
                </Table.Td>
                <Table.Td>
                  {task.overdue ? (
                    <Badge color="red">Прострочено: {formatDate(task.due_date)}</Badge>
                  ) : task.due_date ? (
                    <Text size="sm">{formatDate(task.due_date)}</Text>
                  ) : (
                    "—"
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </>
  );
}
