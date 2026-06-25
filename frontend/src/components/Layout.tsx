import { AppShell, Badge, Button, Group, NavLink, Select, Text, Title } from "@mantine/core";
import { Link, Outlet, useLocation } from "react-router-dom";
import type { MyTask, SystemBrief } from "../api";
import { hasPermission, useAuth } from "../auth";
import { useFetch } from "./shared";
import { useSystem } from "../systemContext";
import { ROLE_LABELS } from "../labels";

const NAV_ITEMS = [
  { to: "/", label: "Дашборд", module: null },
  { to: "/my-tasks", label: "Мої задачі", module: null },
  { to: "/risks", label: "Ризики", module: "risks" },
  { to: "/controls", label: "Контролі", module: "controls" },
  { to: "/gap-analysis", label: "Gap-аналіз", module: "frameworks" },
  { to: "/audits", label: "Аудити", module: "audits" },
  { to: "/policies", label: "Політики", module: "policies" },
  { to: "/reports", label: "Звіти", module: "reports" },
  { to: "/audit-log", label: "Журнал дій", module: "audit_log" },
  { to: "/ai-search", label: "AI-пошук", module: null },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const { systemId, setSystemId } = useSystem();
  const { data: systems } = useFetch<SystemBrief[]>("/systems");
  const { data: tasks } = useFetch<MyTask[]>("/my-tasks");
  const taskCount = tasks?.length ?? 0;

  const items = NAV_ITEMS.filter(
    (item) => !item.module || hasPermission(user, item.module, "read"),
  ).map(({ to, label }) => ({ to, label }));
  if (hasPermission(user, "admin", "manage")) {
    items.push({ to: "/systems", label: "Системи (ІКС)" });
    items.push({ to: "/baselines", label: "Базові набори" });
    items.push({ to: "/frameworks", label: "Каталоги" });
    items.push({ to: "/users", label: "Користувачі" });
    items.push({ to: "/roles", label: "Ролі" });
    items.push({ to: "/api-tokens", label: "API-токени" });
  }

  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 220, breakpoint: "sm" }} padding="md">
      <AppShell.Header p="sm">
        <Group justify="space-between">
          <Group>
            <Title order={3}>GRC</Title>
            <Select
              size="xs"
              w={240}
              data={[
                { value: "", label: "Вся організація" },
                ...(systems?.map((s) => ({ value: String(s.id), label: s.name })) ?? []),
              ]}
              value={systemId ? String(systemId) : ""}
              onChange={(value) => setSystemId(value ? Number(value) : null)}
              allowDeselect={false}
            />
          </Group>
          <Group gap="xs">
            <Text size="sm">{user?.full_name}</Text>
            <Badge variant="light">{user ? ROLE_LABELS[user.role] : ""}</Badge>
            <Button variant="subtle" size="xs" onClick={logout}>
              Вийти
            </Button>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs">
        {items.map((item) => (
          <NavLink
            key={item.to}
            component={Link}
            to={item.to}
            label={
              item.to === "/my-tasks" && taskCount > 0 ? (
                <Group gap={6}>
                  <span>{item.label}</span>
                  <Badge size="xs" color="red" circle>
                    {taskCount}
                  </Badge>
                </Group>
              ) : (
                item.label
              )
            }
            active={
              item.to === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.to)
            }
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
